import os
from flask import Flask, json, jsonify, request
import redis
from mirrcore.data_storage import DataStorage
from mirrcore.attachment_saver import AttachmentSaver
from mirrserver.put_results_validator import PutResultsValidator
from mirrserver.exceptions import InvalidResultsException
from mirrserver.exceptions import InvalidClientIDException
from mirrserver.exceptions import MissingClientIDException
from mirrserver.exceptions import NoJobsException
from mirrserver.get_client_id_validator import GetClientIDValidator
from mirrserver.get_job_validator import GetJobValidator


class WorkServer:
    """
    Class between the client and the work generator.
    Handles the client's request to get a job, client id,
    and put job results.

    Attributes
    ----------
    app : Flask
        the flask app housing all 3 endpoints
    redis : redis
        the redis server holding the jobs waiting queue and client ids
    data : DataStorage
        the data storage class that connects to mongo
    attachment_saver : AttachmentSaver
        the attachment saver class that saves attachments
    put_results_validator : PutResultsValidator
        the validator class for the put results endpoint
    get_client_id_validator : GetClientIDValidator
        the validator class for the get client id endpoint
    get_job_validator : GetJobValidator
        the validator class for the get job endpoint

    Methods
    -------
    __init__(self, redis_server)
        initializes the flask app, redis server
        data storage, attachment saver, and validators

    """
    def __init__(self, redis_server):
        """
        Parameters
        ----------
        redis_server : redis
            the redis server holding the jobs waiting queue and client ids
        """
        self.app = Flask(__name__)
        self.redis = redis_server
        self.data = DataStorage()
        self.attachment_saver = AttachmentSaver()
        self.put_results_validator = PutResultsValidator()
        self.get_client_id_validator = GetClientIDValidator()
        self.get_job_validator = GetJobValidator()


def check_for_database(workserver):
    """
    Checks if the database is connected
    if not this raises an exception

    Parameters
    ----------
    workserver : WorkServer
        the work server class

    Raises
    ------
    ConnectionError
        if the database is not connected
    """
    workserver.redis.ping()


def check_valid_request_client_id(workserver, client_id):
    """
    Checks if the client id is valid
    calls the check_client_id_valid function

    Parameters
    ----------
    workserver : WorkServer
        the work server class
    client_id : int
        the client id validating

    Returns
    -------
    True or False : bool
        True if the client id is valid, False if not
        False will also return an error message
    """
    if not check_client_id_is_valid(workserver, client_id):
        return False, jsonify({'error': 'Invalid client ID'}), 401
    return (True,)


def decrement_count(workserver, job_type):
    """
    for each job type, when that type of job is taken, remove one from
    its redis queue

    Parameters
    ----------
    workserver : WorkServer
        the work server class

    """
    if job_type == 'attachments':
        workserver.redis.decr('num_jobs_attachments_waiting')
    elif job_type == 'comments':
        workserver.redis.decr('num_jobs_comments_waiting')
    elif job_type == 'documents':
        workserver.redis.decr('num_jobs_documents_waiting')
    elif job_type == 'dockets':
        workserver.redis.decr('num_jobs_dockets_waiting')


def get_job(workserver):
    # pylint: disable=R0914
    """
    Takes client's put endpoints validates whether or not its a usable job
    if so it returns the job with the job ID, URL job_type and
    regulations id and agency so the job can be linked to related data
    in the databases

    Parameters
    ----------
    workserver : WorkServer
        the work server class

    Returns
    -------
    if valid job:
        True, job_id, url, job_type, reg_id, agency
    else:
        {'error': 'Client ID was not provided'}, 401
        {'error': 'No jobs available'}, 403
    """
    check_for_database(workserver)
    client_id = request.args.get('client_id')
    success, *values = check_valid_request_client_id(workserver, client_id)
    if not success:
        return False, values[0], values[1]
    if workserver.redis.llen('jobs_waiting_queue') == 0:
        return False, jsonify({'error': 'No jobs available'}), 403
    job = json.loads(workserver.redis.rpop('jobs_waiting_queue'))
    job_id = job['job_id']
    url = job['url']
    agency = job['agency'] if job.get('agency') else "other_agency"
    reg_id = job['reg_id'] if job.get('reg_id') else "other_reg_id"

    job_type = job.get('job_type', 'other')
    workserver.redis.hset('jobs_in_progress', job_id, url)
    workserver.redis.hset('client_jobs', job_id, client_id)

    decrement_count(workserver, job_type)

    return True, job_id, url, job_type, reg_id, agency


def check_results(workserver, data, client_id):
    """
    checks that a result has a valid directory structure in the results key.
    Used for comments, documents, and dockets jobs
    so they know where to be saved to disk.

    Parameters
    ----------
    workserver : WorkServer
        the work server class
    data : dict
        the results data
    client_id : int
        the client id

    Returns
    -------

    if valid results:
        True, directory[:filename_start]
    else one of these options:
        {'error': 'The job being completed was not in progress'}
        {'error': 'No directory was included or was incorrect'}
        {'error': 'The client ID was incorrect'}
    """
    directory = data.get('directory')
    if directory is not None:
        filename_start = directory.rfind('/')
    if directory is None or filename_start == -1:
        error = {'error': 'No directory was included or was incorrect'}
        return False, jsonify(error), 403
    job_id = data.get('job_id', -1)
    expected_client_id = workserver.redis.hget('client_jobs', job_id)
    if (workserver.redis.hget('jobs_in_progress', job_id) is None or
            expected_client_id is None):
        error = {'error': 'The job being completed was not in progress'}
        return False, jsonify(error), 403
    if client_id != int(expected_client_id):
        error = {'error': 'The client ID was incorrect'}
        return False, jsonify(error), 403
    return (True, directory[:filename_start])


def write_results(directory, path, data):
    """
    writes the results to disk. used by docket document and comment jobs

    Parameters
    ----------
    directory : str
        the directory to write the results to
    path : str
        the path to the directory
    data : dict
        the results data to be written to disk
    """
    try:
        os.makedirs(f'/data/{directory}')
    except FileExistsError:
        print(f'Directory already exists in root: /data/{directory}')
    with open(f'/data/{path}', 'w+', encoding='utf8') as file:
        file.write(json.dumps(data))


def check_received_result(workserver):
    check_for_database(workserver)
    client_id = request.args.get('client_id')
    success, *values = check_valid_request_client_id(workserver, client_id)
    if not success:
        return False, values[0], values[1]
    return True, client_id


def put_results(workserver, data):
    success, *values = check_received_result(workserver)
    if not success:
        return success, values[0], values[1]
    if 'error' in data['results'] or 'errors' in data['results']:
        job_id = data['job_id']
        result = workserver.redis.hget('jobs_in_progress', job_id)
        workserver.redis.hdel('jobs_in_progress', job_id)
        workserver.redis.hset('invalid_jobs', job_id, result)
        return (True,)
    success, *results = check_results(workserver, data, int(values[0]))
    if not success:
        return (success, *results)
    job_id = data['job_id']
    workserver.redis.hdel('jobs_in_progress', job_id)
    write_results(results[0], data['directory'], data['results'])
    workserver.data.add(data['results'])
    return (True,)


def put_attachment_results(workserver, data):
    """
    Called to handle the functionality for an attachment job.
    Writes the results to disk and adds the results to the database.
    deletes the job from the redis job in progress queue

    Parameters
    ----------

    workserver : WorkServer
        the work server class
    data : dict
        the results data

    Returns
    -------
    if valid client id:
        True
    else:
        {'error': 'The client ID was incorrect'}, 401
    """
    success, *values = check_received_result(workserver)
    if not success:
        return success, values[0], values[1]
    job_id = data['job_id']
    workserver.redis.hdel('jobs_in_progress', job_id)
    if data.get('results') is not None:
        print('agency', data['agency'])
        print('reg_id', data['reg_id'])
        workserver.attachment_saver.save(
            data, f"/data/{data['agency']}/{data['reg_id']}")
    workserver.data.add_attachment(data)
    return (True,)


def get_client_id(workserver):
    """
    called when a client is started and needs a client id.
    Increments the total number of clients and gives
    the number to the client.


    Parameters
    ----------
    workserver : WorkServer
        the work server class

    Returns
    -------
    client_id : int
        the client id generated for the client
    """
    check_for_database(workserver)
    workserver.redis.incr('total_num_client_ids')
    return True, int(workserver.redis.get('total_num_client_ids'))


def check_client_id_is_valid(workserver, client_id):
    """
    checks that the client id is lower than the
    total number of clients and higher than 0

    Parameters
    ----------
    workserver : WorkServer
        the work server class
    client_id : int
        the client id

    Returns
    -------
    bool if the client id is valid
    """
    check_for_database(workserver)
    num_ids = workserver.redis.get('total_num_client_ids')
    total_ids = 0 if num_ids is None else int(num_ids)
    client_id = int(client_id)
    return 0 < client_id <= total_ids


def create_server(database):
    """
    Create Flask server, add endpoints, and return the server

    Parameters
    ----------
    database : redis
        the redis database

    Returns
    -------
    server : Flask
        the flask server
    """
    workserver = WorkServer(database)

    @workserver.app.route('/get_job', methods=['GET'])
    def _get_job():
        """
        The endpoint a client calls when requesting a job
        Handles the validation of json here and
        then does functionality in the get_job function

        Returns
        -------
        response : json
            {'job': {job_id: url, 'job_type': job_type}}
        """
        try:
            client_id = request.args.get('client_id')
            workserver.get_job_validator.check_get_jobs(client_id)
            success, *values = get_job(workserver)
            if not success:
                return tuple(values)
        except (MissingClientIDException, NoJobsException) as error:
            return jsonify(error.message), error.status_code
        except redis.exceptions.ConnectionError:
            return jsonify({'error': 'Cannot connect to the database'}), 500
        return jsonify({'job_id': str(values[0]),
                        'url':  values[1],
                        'job_type': values[2],
                        'reg_id': values[3],
                        'agency': values[4]}), 200

    @workserver.app.route('/put_results', methods=['PUT'])
    def _put_results():
        """
        The endpoint a client calls when returning with job results
        Handles the validation of json here and
        then does functionality in the put_results function

        Returns
        -------
        response : tuple(json, string)
            status code and message
        """
        data = json.loads(request.get_json())
        try:
            validator = workserver.put_results_validator.\
                check_put_results(data, request.args.get('client_id'))
        except (InvalidResultsException, InvalidClientIDException,
                MissingClientIDException) as invalid_result:
            return jsonify(invalid_result.message), invalid_result.status_code
        # Added ternary instead of if/else to appease pylint too many statements
        success, *values = put_attachment_results(workserver, data) if \
            data.get('job_type') == 'attachments' else \
            put_results(workserver, data)
        if not success:
            return tuple(values)
        return jsonify(validator[0]), validator[1]

    @workserver.app.route('/get_client_id', methods=['GET'])
    def _get_client_id():
        """
        The endpoint a client calls when requesting a client ID

        Returns
        -------
        response : json
            if success:
                {'client_id': client_id}, status code
            if error:
                {'error': 'Cannot connect to the database'}), 500
        """
        try:
            success, *values = get_client_id(workserver)
            if not success:
                return tuple(values)
            return jsonify({'client_id': values[0]}), 200
        except redis.exceptions.ConnectionError:
            return jsonify({'error': 'Cannot connect to the database'}), 500

    return workserver


if __name__ == '__main__':
    try:
        r = redis.Redis('redis')
        r.keys('*')
        server = create_server(r)
        server.app.run(host='0.0.0.0', port=8080, debug=False)
    except redis.exceptions.ConnectionError:
        print('There is no Redis database to connect to.')
