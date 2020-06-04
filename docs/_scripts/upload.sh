pclean
prestart

source ./base.sh

# Upload your file, optionally specifying a repository
export TASK_URL=$(http --form POST $BASE_ADDR/pulp/api/v3/python/upload/ file@../../shelf_reader-0.1-py2-none-any.whl relative_path=shelf_reader-0.1-py2-none-any.whl | \
	jq -r '.task')

wait_until_task_finished $BASE_ADDR$TASK_URL

# If you want to copy/paste your way through the guide,
# create an environment variable for the repository URI.
export CONTENT_HREF=$(http $BASE_ADDR$TASK_URL | jq -r '.created_resources | first')

# Let's inspect our newly created content.
http $BASE_ADDR$CONTENT_HREF
