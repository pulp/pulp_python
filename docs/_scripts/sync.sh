# Using the Remote we just created, we kick off a sync task
export TASK_URL=$(http POST $BASE_ADDR$REPO_HREF'sync/' remote=$REMOTE_HREF mirror=False \
  | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
# When the task is complete, it gives us a new repository version
wait_until_task_finished $BASE_ADDR$TASK_URL
echo "Set REPOVERSION_HREF from finished task."
export REPOVERSION_HREF=$(http $BASE_ADDR$TASK_URL| jq -r '.created_resources | first')

# Lets inspect our newly created RepositoryVersion
http $BASE_ADDR$REPOVERSION_HREF
