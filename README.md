# Slack LTI Tool for Canvas

The Slack LTI Tool for Canvas lets instructors provision Slack Enterprise Grid workspaces for their courses.

## Quick start

To run locally for testing and development:

* Get a Slack API token with admin scopes (details tbd). Set an environment variable: 
```SLACK_API_TOKEN=your-token-here```
* Install requirements (typically in a `virtualenv`): 
```pip install -r requirements.txt```
* Create the database: 
```./manage.py migrate```
* Run the development server: 
```./manage.py runsslserver```
* Get the XML tool configuration from `<your local hostname>/slack_provisioning/tool_config`
* Install the tool in a Canvas course 

## Next steps

* Use a production-class database
* Review the settings and make sure they're appropriate for a production environment.


