# -*- coding: utf-8 -*-
import random
import utils
import settings
import datetime
import logging
from django.db import models
from django.contrib.auth.models import User
from django.db import connection
from contextlib import closing

LOGGER = logging.getLogger(__name__)


class GroupManager(models.Manager):

    def answers_per_value(self, group_name):
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                '''
                SELECT
                    COUNT(geography_answer.id) AS answer_count,
                    geography_ab_value.value AS value
                FROM
                    geography_ab_value
                    INNER JOIN geography_ab_group ON
                        geography_ab_group.id = geography_ab_value.group_id
                    LEFT JOIN geography_ab_uservalues_values ON
                        geography_ab_uservalues_values.value_id = geography_ab_value.id
                    LEFT JOIN geography_ab_uservalues ON
                        geography_ab_uservalues_values.uservalues_id = geography_ab_uservalues.id
                    LEFT JOIN geography_answer ON
                        geography_answer.user_id = geography_ab_uservalues.user_id
                WHERE
                    geography_ab_group.name = %s
                GROUP BY
                    geography_ab_value.id
                ''', [str(group_name)])
            rows = utils.fetchall(cursor)
            return dict([(r['value'], r['answer_count']) for r in rows])

    def users_per_value(self, group_name):
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                '''
                SELECT
                    COUNT(geography_ab_uservalues.user_id) AS user_count,
                    geography_ab_value.value AS value
                FROM
                    geography_ab_value
                    INNER JOIN geography_ab_group ON
                        geography_ab_group.id = geography_ab_value.group_id
                    LEFT JOIN geography_ab_uservalues_values ON
                        geography_ab_uservalues_values.value_id = geography_ab_value.id
                    LEFT JOIN geography_ab_uservalues ON
                        geography_ab_uservalues_values.uservalues_id = geography_ab_uservalues.id
                WHERE
                    geography_ab_group.name = %s
                GROUP BY
                    geography_ab_value.id
                ''', [str(group_name)])
            rows = utils.fetchall(cursor)
            return dict([(r['value'], r['user_count']) for r in rows])

    def init_group(self, name, default_value, values, active=True, max_answers=0, min_answers=0):
        total_prob = sum([probability for (probability, value) in values])
        if total_prob != 100:
            raise Exception('Total probability has to be equal to 100, it was ' + str(total_prob))
        try:
            group = Group(
                name=name,
                active=active,
                max_answers=max_answers,
                min_answers=min_answers)
            group.save()
            default_used = False
            for probability, value in values:
                if value == default_value:
                    if default_used:
                        raise Exception("can't have more than one default value")
                    default_used = True
                value = Value(
                    group=group,
                    value=value,
                    probability=probability,
                    is_default=(value==default_value))
                value.save()
            if not default_used:
                raise Exception('there is no default value')
            return group
        except Exception:
            if group.id:
                with closing(connection.cursor()) as cursor:
                    cursor.execute(
                        '''
                        DELETE FROM geography_ab_value
                        WHERE group_id = %s
                        ''',
                        [group.id])
                    group.delete()
            raise


class Group(models.Model):

    active = models.BooleanField(default=True)
    name = models.CharField(max_length=100, unique=True)
    max_answers = models.IntegerField(default=0)
    min_answers = models.IntegerField(default=0)

    objects = GroupManager()

    class Meta:
        db_table = 'geography_ab_group'
        app_label = 'geography'


class Value(models.Model):

    group = models.ForeignKey(Group)
    value = models.CharField(max_length=100, unique=True)
    probability = models.IntegerField(default=0)
    is_default = models.BooleanField()

    def __str__(self):
        return str(self.value)

    class Meta:
        db_table = 'geography_ab_value'
        app_label = 'geography'


class UserValuesManager(models.Manager):

    def load_user_values(self, user):
        user_values = self.for_user(user)
        defaults = self._prepare_defaults()
        defaults_v = [d.value for d in defaults]
        users = self._prepare_user_values(user_values)
        return defaults + filter(lambda v: v.value not in defaults_v, users)

    def for_user(self, user):
        try:
            return self.select_related('values').get(user_id=user.id)
        except UserValues.DoesNotExist:
            user_values = UserValues(user_id=user.id)
            user_values.save()
            return user_values

    def _choose_value(self, prob_values):
        choice = random.randint(0, 100)
        sum_prob = 0
        for ab_v in prob_values:
            sum_prob += ab_v['probability']
            if choice <= sum_prob:
                return ab_v
        raise Exception('no value chosen')

    def _prepare_defaults(self):
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                '''
                SELECT
                    geography_ab_value.id,
                    geography_ab_value.probability,
                    geography_ab_value.group_id,
                    geography_ab_value.value
                FROM
                    geography_ab_value
                    INNER JOIN geography_ab_group ON
                        geography_ab_group.id = geography_ab_value.group_id
                WHERE
                    geography_ab_value.is_default AND NOT geography_ab_group.active
                GROUP BY geography_ab_value.id
                ''')
            return [
                Value(
                    value=d['value'],
                    id=d['id'],
                    probability=d['probability'],
                    group_id=d['group_id']) for d in utils.fetchall(cursor)
            ]

    def _prepare_user_values(self, user_values):
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                '''
                SELECT COUNT(id) AS num_answers FROM geography_answer WHERE user_id = %s
                ''', [user_values.user_id])
            num_answers = utils.fetchone(cursor)['num_answers']
            cursor.execute(
                '''
                SELECT
                    geography_ab_value.id,
                    geography_ab_value.is_default,
                    geography_ab_value.probability,
                    geography_ab_value.group_id,
                    geography_ab_group.max_answers,
                    geography_ab_group.min_answers
                FROM
                    geography_ab_value
                    INNER JOIN geography_ab_group ON
                        geography_ab_group.id = geography_ab_value.group_id
                WHERE geography_ab_group.id NOT IN (
                    SELECT
                        geography_ab_value.group_id
                    FROM geography_ab_uservalues
                    INNER JOIN geography_ab_uservalues_values ON
                        geography_ab_uservalues.id = geography_ab_uservalues_values.uservalues_id
                    INNER JOIN geography_ab_value ON
                        geography_ab_value.id = geography_ab_uservalues_values.value_id
                    WHERE geography_ab_uservalues.user_id = %s)
                    AND geography_ab_group.active
                GROUP BY geography_ab_value.id;
                ''', [user_values.user_id])
            ab_values = {}
            ab_values_default = {}
            ab_value = utils.fetchone(cursor)
            user_values_defaults = []
            while ab_value:
                if ab_value and ab_value['is_default']:
                    ab_values_default[ab_value['group_id']] = ab_value
                group_values = ab_values.get(ab_value['group_id'], [])
                group_values.append(ab_value)
                ab_values[ab_value['group_id']] = group_values
                ab_value = utils.fetchone(cursor)
            updated = False
            for (group_id, group_values) in ab_values.iteritems():
                if (not group_values[0]['min_answers'] or num_answers >= group_values[0]['min_answers']) and (not group_values[0]['max_answers'] or num_answers <= group_values[0]['max_answers']):
                    chosen_value = self._choose_value(group_values)
                    user_values.values.add(Value.objects.get(id=chosen_value['id']))
                    updated = True
                else:
                    user_values_defaults.append(Value.objects.get(id=ab_values_default[group_id]['id']))
            if updated:
                user_values.save()
            return list(user_values.values.get_query_set()) + user_values_defaults


class UserValues(models.Model):

    user = models.ForeignKey(User)
    values = models.ManyToManyField(Value)
    objects = UserValuesManager()

    class Meta:
        db_table = 'geography_ab_uservalues'
        app_label = 'geography'


class ABEnvironment:

    def __init__(self, request):
        self._request = request
        self._used = {}

    def is_member_of(self, ab_value, reason):
        is_member = any([v.value == ab_value for v in self._request.session['ab_values']])
        if is_member:
            affecting = self._used.get(reason, [])
            affecting.append(ab_value)
            self._used[reason] = affecting
        return is_member

    def get_membership(self, ab_values, default_value, reason):
        for v in self._request.session['ab_values']:
            if v.value in ab_values:
                affecting = self._used.get(reason, [])
                affecting.append(v)
                self._used[reason] = affecting
                return v.value
        return default_value

    def get_affecting_values(self, reason):
        return self._used.get(reason, [])

    @staticmethod
    def init_session(user, session):
        if not settings.DEBUG and (
                ('ab_values_modified' in session.keys() and (session['ab_values_modified'] - datetime.datetime.now()).total_seconds() <= 15 * 60)
                or ('ab_values_user_id' in session.keys() and session['ab_values_user_id'] != user.id)):
            return session
        user_values = UserValues.objects.load_user_values(user)
        session['ab_values'] = user_values
        session['ab_values_modified'] = datetime.datetime.now()
        session['ab_values_user_id'] = user.id
        LOGGER.debug(
            'init values AB values for user %s: %s',
            user, session['ab_values'])
        return session
