#!/bin/bash
SELF=$0
SELF_DIR=`dirname $SELF`
if [ $GEOGRAPHY_WORKSPACE_DIR ]; then
	WORKSPACE_DIR=$GEOGRAPHY_WORKSPACE_DIR;
else
	WORKSPACE_DIR=$SELF_DIR/..
fi
APP_DIR="$WORKSPACE_DIR/main"

if [ "$GEOGRAPHY_DATA_DIR" ]; then
	DATA_DIR="$GEOGRAPHY_DATA_DIR"
else
	DATA_DIR="$APP_DIR"
fi

DEST_FILE=$DATA_DIR/`date +"%Y-%m-%d_%H-%M-%S"`.sql

mysqldump -p$GEOGRAPHY_DATABASE_PASSWORD -u$GEOGRAPHY_DATABASE_USER -h$GEOGRAPHY_DATABASE_HOST -P$GEOGRAPHY_DATABASE_PORT $GEOGRAPHY_DATABASE_NAME > $DEST_FILE

echo $DEST_FILE
