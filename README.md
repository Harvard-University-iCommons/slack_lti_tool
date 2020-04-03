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

Note: the tool will need to be able to set a session cookie which may be difficult given current browser cross-site tracking limits. If possible, run the server on a hostname that shares the same root domain as your Canvas instance. 

## Next steps

* Use a production-class database
* Use a production-class WSGI server, such as gunicorn. 
* Review the settings and make sure they're appropriate for a production environment.


