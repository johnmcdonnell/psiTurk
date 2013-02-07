
import os
import platform
import datetime
import logging
from functools import wraps, update_wrapper
from random import choice
from collections import Counter

# Importing flask
from flask import Flask, render_template, request, Response, make_response, jsonify, current_app, send_from_directory

# Database setup
from db import db_session
from models import Participant
from sqlalchemy import or_

# Configuration:
from config import config

# Actual task file
import task

if platform.uname()[1] == "puncture":
    os.chdir('/srv/wsgi/tvTurk')

# Set up logging
logfilepath = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'server.log')

loglevels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL]
loglevel = loglevels[config.getint('User Preferences', 'loglevel')]
logging.basicConfig( filename=logfilepath, format='%(asctime)s %(message)s', level=loglevel )

# config.get( 'Mechanical Turk Info', 'aws_secret_access_key' )

# constants
DEPLOYMENT_ENV = config.getint('User Preferences', 'loglevel')
CODE_VERSION = config.getfloat('Task Parameters', 'code_version')


# Database configuration and constants
TABLENAME = config.get('Database Parameters', 'table_name')
SUPPORTIE = config.getboolean('Server Parameters', 'support_IE')

# Status codes
ALLOCATED = 1
STARTED = 2
COMPLETED = 3
DEBRIEFED = 4
CREDITED = 5
QUITEARLY = 6
REJECTED = 7


app = Flask(__name__)

#----------------------------------------------
# function for authentication
#----------------------------------------------
queryname = config.get('Server Parameters', 'login_username')
querypw = config.get('Server Parameters', 'login_pw')

def wrapper(func, args):
    return func(*args)

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == queryname and password == querypw

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    """
    Decorator to prompt for user name and password. Useful for data dumps, etc.
    that you don't want to be public.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

#----------------------------------------------
# ExperimentError Exception, for db errors, etc.
#----------------------------------------------
# Possible ExperimentError values.
experiment_errors = dict(
    status_incorrectly_set = 1000,
    hit_assign_worker_id_not_set_in_mturk = 1001,
    hit_assign_worker_id_not_set_in_consent = 1002,
    hit_assign_worker_id_not_set_in_exp = 1003,
    hit_assign_appears_in_database_more_than_once = 1004,
    already_started_exp = 1008,
    already_started_exp_mturk = 1009,
    already_did_exp_hit = 1010,
    tried_to_quit= 1011,
    intermediate_save = 1012,
    improper_inputs = 1013,
    page_not_found = 404,
    in_debug = 2005,
    unknown_error = 9999
)

class ExperimentError(Exception):
    """
    Error class for experimental errors, such as subject not being found in
    the database.
    """
    def __init__(self, value):
        self.value = value
        self.errornum = experiment_errors[self.value]
    def __str__(self):
        return repr(self.value)
    def error_page(self, request):
        return render_template('error.html', 
                               errornum=self.errornum, 
                               **request.args)

@app.errorhandler(ExperimentError)
def handleExpError(e):
    """Handle errors by sending an error page."""
    return e.error_page( request )

#----------------------------------------------
# DB setup
#----------------------------------------------
@app.teardown_request
def shutdown_session(exception=None):
    db_session.remove()

#----------------------------------------------
# general utilities
#----------------------------------------------
def get_people(people):
    if not people:
        return []
    for record in people:
        person = {}
        for field in ['subjid', 'ipaddress', 'hitid', 'assignmentid',
                      'workerid', 'cond', 'counterbalance',
                      'beginhit','beginexp', 'endhit', 'status', 'datastring']:
            if field=='datastring':
                if record[field] == None:
                    person[field] = "Nothing yet"
                else:
                    person[field] = record[field][:10]
            else:
                person[field] = record[field]
        people.append( person )
    return people

#----------------------------------------------
# Experiment counterbalancing code.
#----------------------------------------------

def get_random_condcount():
    """
    HITs can be in one of three states:
        - jobs that are finished
        - jobs that are started but not finished
        - jobs that are never going to finish (user decided not to do it)
    Our count should be based on the first two, so we count any tasks finished
    or any tasks not finished that were started in the last cutoff_time
    minutes, as specified in the cutoff_time variable in the config file.
    
    Returns a tuple: (cond, condition)
    """
    
    cutofftime = datetime.timedelta(minutes=-config.getint('Server Parameters', 'cutoff_time'))
    starttime = datetime.datetime.now() + cutofftime
    
    numconds = config.getint('Task Parameters', 'num_conds')
    numcounts = config.getint('Task Parameters', 'num_counters')
    
    participants = Participant.query.\
                   filter(Participant.codeversion == CODE_VERSION).\
                   filter(or_(Participant.status == 4, 
                              Participant.status == 5, 
                              Participant.beginhit > starttime)).\
                   filter(Participant.cond<4).\
                   all()
    counts = Counter()
    for cond in range(numconds):
        for counter in range(numcounts):
            counts[(cond, counter)] = 0
    for p in participants:
        counts[(p.cond, p.counterbalance)] += 1
    mincount = min( counts.values() )
    minima = [hash for hash, count in counts.iteritems() if count == mincount]
    chosen = choice(minima)
    #conds += [ 0 for _ in range(1000) ]
    #conds += [ 1 for _ in range(1000) ]
    print "given ", counts, " chose ", chosen
    
    return chosen

#----------------------------------------------
# routes
#----------------------------------------------

@app.route('/error', methods = ['GET'])
def give_error():
    """
    Just replaces the 500 screen.
    """
    return render_template('error.html', errornum=500 )


@app.route('/debug', methods = ['GET'])
def start_exp_debug():
    # this serves up the experiment applet in debug mode
    if "cond" in request.args.keys():
        subj_cond = int( request.args['cond'] );
    else:
        import random
        subj_cond = random.randrange(12);
    if "subjid" in request.args.keys():
        counterbalance = int( request.args['counterbalance'] );
    else:
        import random
        counterbalance = random.randrange(384);
    return render_template('exp.html', 
                           subj_num = -1, 
                           traintype = 0 if subj_cond<6 else 1, 
                           rule = subj_cond%6, 
                           dimorder = counterbalance%24, 
                           dimvals = counterbalance//24,
                           skipto = request.args['skipto'] if 'skipto' in request.args else '',
                           imagefiles = os.listdir("static/images")
                          )

@app.route('/mturk', methods=['GET'])
def mturkroute():
    """
    This is the url we give for our 'external question'.
    This page will be called from within mechanical turk, with url arguments
    hitId, assignmentId, and workerId. 
    If the worker has not yet accepted the hit:
      These arguments will have null values, we should just show an ad for the
      experiment.
    If the worker has accepted the hit:
      These arguments will have appropriate values and we should enter the person
      in the database and provide a link to the experiment popup.
    """
    if not SUPPORTIE:
        # Handler for IE users if IE is not supported.
        if request.user_agent.browser == "msie":
            return render_template( 'ie.html' )
    if not (request.args.has_key('hitId') and request.args.has_key('assignmentId')):
        raise ExperimentError('hit_assign_worker_id_not_set_in_mturk')
    # Person has accepted the HIT, entering them into the database.
    hitId = request.args['hitId']
    assignmentId = request.args['assignmentId']
    if request.args.has_key('workerId'):
        workerId = request.args['workerId']
        # first check if this workerId has completed the task before (v1)
        nrecords = Participant.query.\
                   filter(Participant.assignmentid != assignmentId).\
                   filter(Participant.workerid == workerId).\
                   count()
        
        if nrecords > 0:
            # already completed task
            raise ExperimentError('already_did_exp_hit')
    else:
        # If worker has not accepted the hit:
        workerId = None
    print hitId, assignmentId, workerId
    try:
        part = Participant.query.\
                           filter(Participant.hitid == hitId).\
                           filter(Participant.assignmentid == assignmentId).\
                           filter(Participant.workerid == workerId).\
                           one()
        status = part.status
        subj_id = part.subjid
    except:
        status = None
        subj_id = None
    
    if status == ALLOCATED or not status:
        # Participant has not yet agreed to the consent. They might not
        # even have accepted the HIT. The mturkindex template will treat
        # them appropriately regardless.
        return render_template('mturkindex.html', 
                               hitid = hitId, 
                               assignmentid = assignmentId, 
                               workerid = workerId)
    elif status == STARTED or status == QUITEARLY:
        # Once participants have finished the instructions, we do not allow
        # them to start the task again.
        raise ExperimentError('already_started_exp_mturk')
    elif status == COMPLETED:
        # They've done the whole task, but haven't signed the debriefing yet.
        return render_template('debriefing.html', 
                               subjid = subj_id)
    elif status == DEBRIEFED:
        # They've done the debriefing but perhaps haven't submitted the HIT yet..
        return render_template('thanks.html', 
                               target_env=DEPLOYMENT_ENV, 
                               hitid = hitId, 
                               assignmentid = assignmentId, 
                               workerid = workerId)
    else:
        raise ExperimentError( "STATUS_INCORRECTLY_SET" )

@app.route('/consent', methods = ['GET'])
def give_consent():
    """
    Serves up the consent in the popup window.
    """
    if not (request.args.has_key('hitId') and request.args.has_key('assignmentId') and request.args.has_key('workerId')):
        raise ExperimentError('hit_assign_worker_id_not_set_in_consent')
    hitId = request.args['hitId']
    assignmentId = request.args['assignmentId']
    workerId = request.args['workerId']
    print "/consent",  hitId, assignmentId, workerId
    return render_template('consent.html', hitid = hitId, assignmentid=assignmentId, workerid=workerId)

def htmlSnippets():
    names = [
        "postquestionnaire",
        "test",
        "intro",
        "antennaintro",
        "antennalength",
        "antennaangle",
        "distribution",
        "instructfinal",
        "testinstruct",
        "prequiz",
        "prefail",
        "presuccess"
    ]
    return dict( (name, render_template(name+".html")) for name in names )

@app.route('/exp', methods=['GET'])
def start_exp():
    """
    Serves up the experiment applet.
    """
    if not (request.args.has_key('hitId') and 
            request.args.has_key('assignmentId') and 
            request.args.has_key('workerId')):
        raise ExperimentError( 'hit_assign_worker_id_not_set_in_exp' )
    hitId = request.args['hitId']
    assignmentId = request.args['assignmentId']
    workerId = request.args['workerId']
    print "/exp", hitId, assignmentId, workerId
    
    # check first to see if this hitId or assignmentId exists.  if so check to see if inExp is set
    matches = Participant.query.\
                        filter(Participant.hitid == hitId).\
                        filter(Participant.assignmentid == assignmentId).\
                        filter(Participant.workerid == workerId).\
                        all()
    numrecs = len(matches)
    if numrecs == 0:
        
        # Choose condition and counterbalance
        subj_cond, subj_counter = get_random_condcount()
        
        if not request.remote_addr:
            myip = "UKNOWNIP"
        else:
            myip = request.remote_addr
        
        # set condition here and insert into database
        part = Participant( hitId, myip, assignmentId, workerId, subj_cond, subj_counter)
        db_session.add( part )
        db_session.commit()
    
    elif numrecs==1:
        part = matches[0]
        if part.status >= STARTED: # in experiment (or later) can't restart at this point
            raise ExperimentError( 'already_started_exp' )
    else:
        print "Error, hit/assignment appears in database more than once (serious problem)"
        raise ExperimentError('hit_assign_appears_in_database_more_than_once')
    
    taskparams = task.condition_builder(part.cond, part.counterbalance)
    taskobject = task.tvTask( ** taskparams )
    
    return render_template('exp.html',
                           subjnum = part.subjid, 
                           subjinfo = [part.subjid] + taskparams.values(),
                           pages = htmlSnippets(), 
                           train = taskobject.train,
                           test = taskobject.test,
                           imagefiles = os.listdir("static/images"))


def crossdomain(origin=None, methods=None, headers=None,
                max_age=21600, attach_to_all=True,
                automatic_options=True):
    if methods is not None:
        methods = ', '.join(sorted(x.upper() for x in methods))
    if headers is not None and not isinstance(headers, basestring):
        headers = ', '.join(x.upper() for x in headers)
    if not isinstance(origin, basestring):
        origin = ', '.join(origin)
    if isinstance(max_age, datetime.timedelta):
        max_age = max_age.total_seconds()

    def get_methods():
        if methods is not None:
            return methods

        options_resp = current_app.make_default_options_response()
        return options_resp.headers['allow']

    def decorator(f):
        def wrapped_function(*args, **kwargs):
            if automatic_options and request.method == 'OPTIONS':
                resp = current_app.make_default_options_response()
            else:
                resp = make_response(f(*args, **kwargs))
            if not attach_to_all and request.method != 'OPTIONS':
                return resp

            h = resp.headers

            h['Access-Control-Allow-Origin'] = origin
            h['Access-Control-Allow-Methods'] = get_methods()
            h['Access-Control-Max-Age'] = str(max_age)
            if headers is not None:
                h['Access-Control-Allow-Headers'] = headers
            return resp

        f.provide_automatic_options = False
        return update_wrapper(wrapped_function, f)
    return decorator

def procitems(items):
    import numpy as np
    ret = []
    for item in items:
        bimod = item[1]
        unimod = item[2]
        abstractChannel = item[3]
        #rectname = {0:"one", 1:"two", 2:"three", 3:"four", 4:"five", 5:"six", 6:"seven", 7:"eight", 8:"nine", 9:"ten"}[item[4]]
        length = item[5]
        angle = item[6]
        if np.isnan(abstractChannel):
            abstractChannel = 'nolab'
        else:
            abstractChannel = float( abstractChannel )
        channel = item[7]
        ret.append( dict(
            bimod = bimod,
            unimod = unimod,
            length = length,
            angle = angle,
            abstractChannel = abstractChannel,
            channel = channel))
    return ret

@app.route('/items')
@crossdomain(origin='*')
def showitems():
    taskparams = task.condition_builder(int(request.args['cond']), int(request.args['count']))
    thetask = task.tvTask( **taskparams )
    return jsonify( train=procitems(thetask.train), test=procitems(thetask.test) )

@app.route('/inexp', methods = ['POST'])
def enterexp():
    """
    AJAX listener that listens for a signal from the user's script when they
    leave the instructions and enter the real experiment. After the server
    receives this signal, it will no longer allow them to re-access the
    experiment applet (meaning they can't do part of the experiment and
    referesh to start over).
    """
    print "/inexp"
    if not request.form.has_key('subjId'):
        raise ExperimentError('improper_inputs')
    subjid = request.form['subjId']
    user = Participant.query.\
            filter(Participant.subjid == subjid).\
            one()
    user.status = STARTED
    user.beginexp = datetime.datetime.now()
    db_session.add(user)
    db_session.commit()
    return "Success"

@app.route('/inexpsave', methods = ['POST'])
def inexpsave():
    """
    The experiments script updates the server periodically on subjects'
    progress. This lets us better understand attrition.
    """
    print "accessing the /inexpsave route"
    print request.form.keys()
    if request.form.has_key('subjId') and request.form.has_key('dataString'):
        subj_id = request.form['subjId']
        datastring = request.form['dataString']  
        print "getting the save data", subj_id, datastring
        user = Participant.query.\
                filter(Participant.subjid == subj_id).\
                one()
        user.datastring = datastring
        user.status = STARTED
        db_session.add(user)
        db_session.commit()
    return render_template('error.html', errornum= experiment_errors['intermediate_save'])

@app.route('/quitter', methods = ['POST'])
def quitter():
    """
    Subjects post data as they quit, to help us better understand the quitters.
    """
    print "accessing the /quitter route"
    print request.form.keys()
    if request.form.has_key('subjId') and request.form.has_key('dataString'):
        subjid = request.form['subjId']
        datastring = request.form['dataString']  
        print "getting the save data", subjid, datastring
        try:
            user = Participant.query.\
                    filter(Participant.subjid == subjid).\
                    one()
            user.datastring = datastring
            user.status = QUITEARLY
            db_session.add(user)
            db_session.commit()
        except:
            return render_template('error.html', errornum= experiment_errors['hit_assign_worker_id_not_set_in_mturk'])
    return render_template('error.html', errornum= experiment_errors['tried_to_quit'])

@app.route('/predebrief', methods = ['POST'])
def savedata():
    """
    User has finished the experiment and is posting their data in the form of a
    (long) string. They will receive a debreifing back.
    """
    if not (request.form.has_key('subjid') and request.form.has_key('data')):
        raise ExperimentError('improper_inputs')
    subjid = int(request.form['subjid'])
    datastring = request.form['data']
    print "/predebrief", subjid, datastring
    
    user = Participant.query.\
            filter(Participant.subjid == subjid).\
            one()
    user.status = COMPLETED
    user.datastring = datastring
    user.endhit = datetime.datetime.now()
    db_session.add(user)
    db_session.commit()
    
    axis = {0: "length", 1: "angle"}[user.counterbalance]
    
    return render_template('predebrief.html', axis=axis, subjid=subjid)

@app.route('/debrief', methods = ['GET'])
def givedebrief():
    """
    Official debriefing
    """
    subjid = request.args['subjid']
    return render_template('debriefing.html', subjid=subjid)

@app.route('/complete', methods = ['POST'])
def completed():
    """
    This is sent in when the participant completes the debriefing. The
    participant can accept the debriefing or declare that they were not
    adequately debriefed, and that response is logged in the database.
    """
    print "accessing the /complete route"
    print request.form.keys()
    if not (request.form.has_key('subjid') and request.form.has_key('agree')):
        raise ExperimentError('improper_inputs')
    subjid = request.form['subjid']
    agreed = request.form['agree']  
    print subjid, agreed
    
    user = Participant.query.\
            filter(Participant.subjid == subjid).\
            one()
    user.status = DEBRIEFED
    user.debriefed = agreed == 'true'
    db_session.add(user)
    db_session.commit()
    return render_template('closepopup.html')

#------------------------------------------------------
# routes for displaying the database/editing it in html
#------------------------------------------------------
@app.route('/list')
@requires_auth
def viewdata():
    """
    Gives a page providing a readout of the database. Requires password
    authentication.
    """
    people = Participant.query.\
              order_by(Participant.subjid).\
              all()
    print people
    people = get_people(people)
    return render_template('simplelist.html', records=people)

@app.route('/updatestatus', methods = ['POST'])
@app.route('/updatestatus/', methods = ['POST'])
def updatestatus():
    """
    Allows subject status to be updated from the web interface.
    """
    if request.method == 'POST':
        field = request.form['id']
        value = request.form['value']
        print field, value
        [tmp, field, subjid] = field.split('_')
        id = int(id)
        
        user = Participant.query.\
                filter(Participant.subjid == subjid).\
                one()
        if field=='status':
            user.status = value
        db_session.add(user)
        db_session.commit()
        
        return value

@app.route('/dumpdata')
@requires_auth
def dumpdata():
    """
    Dumps all the data strings concatenated. Requires password authentication.
    """
    ret = '\n'.join([subj.datastring for subj in Participant.query.all()])
    response = make_response( ret )
    response.headers['Content-Disposition'] = 'attachment;filename=data.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response

#----------------------------------------------
# generic route
#----------------------------------------------
@app.route('/<pagename>')
def regularpage(pagename = None):
    """
    Route not found by the other routes above. May point to a static template.
    """
    if pagename==None:
        raise ExperimentError('page_not_found')
    return render_template(pagename)

#----------------------------------------------
# favicon issue - http://flask.pocoo.org/docs/patterns/favicon/
#----------------------------------------------
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                'favicon.ico', mimetype='image/vnd.microsoft.icon')

###########################################################
# let's start
###########################################################
if __name__ == '__main__':
    from db import init_db
    init_db()
    
    print "Starting webserver."
    app.run(debug=config.getboolean('Server Parameters', 'debug'), host='0.0.0.0', port=config.getint('Server Parameters', 'port'))

# vim: expandtab sw=4 ts=4
