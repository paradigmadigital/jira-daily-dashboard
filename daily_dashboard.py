import arrow
import datetime
from jira.client import JIRA
from flask import Flask, render_template

from constants import JIRA_PROJECT, JIRA_BOARD, JIRA_STATUSES, BANNED_MEMBERS, SCRUM_MASTER, GENERIC_ACCOUNT, \
    SCRUM_MASTER_DEDICATION_PERCENTAGE
from credentials import JIRA_SERVER, JIRA_USER, JIRA_PASSWORD

app = Flask(__name__)


settings = {'basic_auth': (JIRA_USER, JIRA_PASSWORD), 'options': {'server': JIRA_SERVER, 'verify': False}}

jira = JIRA(**settings)


@app.route('/', defaults={'username': None})
@app.route('/<username>')
def index(username):
    sprint = [sprint for sprint in jira.sprints(JIRA_BOARD) if sprint.state == 'ACTIVE'][-1]
    sprint_info = jira.sprint_info(JIRA_BOARD, sprint.id)

    members = get_members()

    issues, issues_by_status = get_issues(sprint, username)

    worklogs_hours, worklogs_status = get_worklogs(issues, username, sprint_info.get('startDate'))

    return render_template('index.html',
                           sprint=sprint,
                           sprint_info=sprint_info,
                           selected_member=username,
                           worklogs_status=worklogs_status,
                           worklogs_hours=worklogs_hours,
                           members=members,
                           statuses=JIRA_STATUSES,
                           issues_by_status=issues_by_status)


def get_members():
    all_members = jira.search_assignable_users_for_issues(username=None, project=JIRA_PROJECT)

    members = [member for member in all_members if 'paradigma' in member.emailAddress and member.key not in BANNED_MEMBERS]

    return members


def get_issues(sprint, username):
    query = 'project = {project} and sprint = "{sprint}"'.format(project=JIRA_PROJECT, sprint=sprint.name)
    if username:
        query += ' and assignee = "{assignee}"'.format(assignee=username)
    query += ' ORDER BY resolutiondate DESC'

    issues = jira.search_issues(query, maxResults=100)

    issues_by_status = {status: [] for status in JIRA_STATUSES}
    for issue in issues:
        issues_by_status[issue.fields.status.name].append(issue.raw)

    return issues, issues_by_status


def get_worklogs(issues, username, sprint_start_date):
    worklogs_time = 0
    worklogs_status = None

    if username is None:
        return worklogs_time, worklogs_status

    for issue in issues:
        worklogs = jira.worklogs(issue)
        for worklog in worklogs:
            if worklog.author.name == username:
                worklogs_time += worklog.timeSpentSeconds

    worklogs_hours = worklogs_time/3600.0

    from_date = arrow.get(sprint_start_date, 'DD/MMM/YY H:m A').date()
    to_date = arrow.now().date()
    days_generator = (from_date + datetime.timedelta(x + 1) for x in xrange((to_date - from_date).days))

    labour_hours = sum(1 for day in days_generator if day.weekday() < 5) * 8
    if username == SCRUM_MASTER:
        labour_hours *= SCRUM_MASTER_DEDICATION_PERCENTAGE

    if worklogs_hours >= labour_hours:
        worklogs_status = 'green'
    elif (worklogs_hours + 16) >= labour_hours:
        worklogs_status = 'orange'
    elif username and username != GENERIC_ACCOUNT:
        worklogs_status = 'red'

    return worklogs_hours, worklogs_status

if __name__ == "__main__":
    app.run(debug=True)
