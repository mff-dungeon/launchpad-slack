# -*- coding: utf-8 -*-

from flask import Flask, request, Response, redirect
from utils import lp_login, _sort
import settings

import os
import simplejson
import requests

app = Flask(__name__)

ALLOWED_EVENTS = [
    'bzr:push:0.1',
]


@app.route('/webhook', methods=['post'])
def webhook():
    lp_event = request.headers.get('X-Launchpad-Event-Type')
    if lp_event is not None and lp_event in ALLOWED_EVENTS:
        # Settings
        webhook = settings.SLACK_INCOMING_WEBHOOKS
        username = settings.SLACK_USERNAME
        icon_url = settings.SLACK_ICON_URL
        channel = settings.SLACK_CHANNEL

        text = None

        if lp_event == 'bzr:push:0.1':
            link = "http://bazaar.launchpad.net/%s/revision/%s" % (
                request.json['bzr_branch_path'], request.json['new']['revision_id'])
            text = "New <%s|commit> has been pushed!" % (link, )

        payload = {
            'text': text
        }

        if username:
            payload['username'] = username.encode('utf-8')

        if channel:
            payload['channel'] = channel

        if icon_url:
            payload['icon_url'] = icon_url

        values = {'payload': simplejson.dumps(payload)}
        requests.post(webhook, data=values)

        return Response("OK", content_type='text/plain; charset=utf-8')
    else:
        return Response("Event not Allowed", content_type='text/plain; charset=utf-8')


@app.route('/lp', methods=['get', 'post'])
def lp():
    id = int(request.values.get('text'))
    token = request.values.get('token')

    if settings.SLACK_COMMANDS_TOKEN and settings.SLACK_COMMANDS_TOKEN != token:
        return Response('Not Allowed.',
                        content_type='text/plain; charset=utf-8')

    lp = lp_login()
    if not lp:
        return Response('Error.',
                        content_type='text/plain; charset=utf-8')

    try:
        bugdata = lp.bugs[id]
        if bugdata.private:
            return Response('This bug is private',
                            content_type='text/plain; charset=utf-8')
        dup = bugdata.duplicate_of
        summary_prefix = ''  # Used to made dups easier
        while dup:
            summary_prefix = 'duplicate for #%d ' % id
            bugdata = dup
            dup = bugdata.duplicate_of

        affected = bugdata.users_affected_count_with_dupes
        heat = bugdata.heat

        tasks = bugdata.bug_tasks

        if tasks.total_size != 1:
            tasks = list(tasks)
            try:
                tasks.sort(_sort)
                taskdata = tasks[-1]
            except ValueError:
                tasks = [
                    _ for _ in tasks if _.bug_target_name.endswith(u'(Ubuntu)')]
                if tasks:
                    if len(tasks) != 1:
                        try:
                            tasks.sort(_sort)
                            taskdata = tasks[-1]
                        except ValueError:
                            taskdata = bugdata.bug_tasks[
                                bugdata.bug_tasks.total_size - 1]
                    else:
                        taskdata = tasks[-1]
                else:
                    taskdata = tasks[-1]
        else:
            taskdata = tasks[0]

        assignee = taskdata.assignee
        t = taskdata.bug_target_display_name  # task name

        if assignee:  # "Diaplay Name (Launchpad ID)"
            assignee = u"%s (%s)" % (assignee.display_name, assignee.name)
        else:
            assignee = ''

    except Exception, e:
        return Response('Error : %s' % e, content_type='text/plain; charset=utf-8')

    extinfo = "(affected: %d, heat: %d)" % (affected, heat)

    (bid, product, title, severity, status, assignee, url, extinfo) = (bugdata.id, t, summary_prefix +
                                                                       bugdata.title, taskdata.importance, taskdata.status, assignee, "https://pad.lv/%s/" % bugdata.id, extinfo)

    severity = severity[0].upper() + severity[1:].lower()
    status = status[0].upper() + status[1:].lower()

    return Response("Bug %s in %s \"%s\" %s [%s,%s] %s" %
                    (bid, product, title, extinfo, severity, status, url),
                    content_type='text/plain; charset=utf-8')


@app.route('/')
def index():
    return redirect('https://github.com/mff-dungeon/launchpad-slack')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
