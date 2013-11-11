"""Cloud Preferences API"""

# Copyright 2013 Trey Tabner
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import motor
import os
import requests
import pylibmc
import hashlib
import logging
import logstash_formatter

import tornado.ioloop
import tornado.web

from tornado import gen
from tornado.options import define, options

USERNAME = os.environ.get('USERNAME')
PASSWORD = os.environ.get('PASSWORD')


GET_ROLES = ['lnx-cbastion', 
             'Windows Bastion Users']

POST_ROLES = ['identity:admin']


define("port", default="8888", help="Port to listen on")
define("url", default=None, help="Keystone Auth Endpoint")
define("mongodb", default="127.0.0.1:27017", help="MongoDB host or hosts")
define("memcached", default="127.0.0.1", help="Memcached host or hosts")
define("database", default="cloudprefs", help="Database name")
define("collection", default=None, help="Force preferences to one collection")
define("log", default='/var/log/cloudprefs.log', help="Logfile path")
define("logtype", default=None, help="Log type")

def get_auth_token(cache=False):
    if cache:
        mc_server = []
        mc_server.append(options.memcached)
        mc = pylibmc.Client(mc_server, binary=True,
                            behaviors={'tcp_nodelay': True, 'ketama': True})
        key = 'token-raxauth_token' 

        try:
            token = mc.get(key)

            if token:
                return token

        except:
            pass

    url = "https://%s/v2.0/tokens" % options.url
    headers = {'content-type': 'application/json'}
    data = {"auth": {"passwordCredentials": {"username": "%s",
                                             "password": "%s"}}}
    res = json.dumps(data) % (USERNAME, PASSWORD)
    r = requests.post(url, res, headers=headers)
    if r.status_code == requests.codes.ok:
        token = r.json()['access']['token']['id']
        if cache:
            mc.set(key, token, time=3600)
        return token
    
    return False 

def validate_token(auth_token, managed_service_token, cache=False):

    if cache:
        mc_server = []
        mc_server.append(options.memcached)
        mc = pylibmc.Client(mc_server, binary=True,
                            behaviors={'tcp_nodelay': True, 'ketama': True})
        key = 'token-%s' % hashlib.sha224(auth_token).hexdigest()

        try:
            token = mc.get(key)

            if token:
                return token

        except:
            pass

    url = "https://%s/v2.0/tokens" % options.url
    headers = {'content-type': 'application/json', 
               'X-Auth-Token':managed_service_token}

    req = url + "/%s" % auth_token
    r = requests.get(req, headers=headers)
    if r.status_code == requests.codes.ok:
        user = r.json()
        if cache:
            mc.set(key, user, time=360)
        return user
    else:
        logging.info('Invalid auth token')
    return False 


class PrefsHandler(tornado.web.RequestHandler):
    """Cloud Preferences Request Handler"""

    @gen.coroutine
    def initialize(self, database):
        """Verify authentication and setup database access"""
        headers = self.request.headers
        self.user_id = headers.get('X-User-Id')
        if options.collection:
            self.collection = database[options.collection]
        else:
            self.collection = database[self.user_id]

    @gen.coroutine
    def prepare(self):
        """Make sure we have a valid collection to work with"""
        if 'collection' not in dir(self):
            self.set_status(401)
            self.finish()

        if options.url:
            managed_service_token = get_auth_token(True)
            headers = self.request.headers
            self.auth_token = headers.get('X-Auth-Token')
            if self.auth_token:
                self.user = validate_token(self.auth_token, managed_service_token, True)
                if self.user:
                    self.roles = self.user['access']['user']['roles']
                    self.user = self.user['access']['user']['id']

                    for y in self.roles:
                        for v in y.items():
                            if v[1] in GET_ROLES:
                                self.access = 'GET'
                                logging.info("User %s granted read access" % self.user)
                                return
                            elif v[1] in POST_ROLES:
                                self.access = 'POST'
                                logging.info("User %s granted write access" % self.user)
                                return                  
        self.set_status(401)
        self.finish() 


    @gen.coroutine
    def get(self, identifier=None, keyword=None):
        """Return a document or part of a document for specified entity"""
        if not self.access and options.url:
            self.set_status(401)
            self.finish() 
            return

        response = None

        if not identifier:
            # List all documents

            if self.request.body:
                try:
                    search = json.loads(self.request.body)
                except:
                    self.set_status(400)
                    return
            else:
                search = {}

            cursor = self.collection.find(search, {'_id': 0, '__id': 1})
            response = []
            results = yield motor.Op(cursor.to_list, length=10)
            for result in results:
                if '__id' in result:
                    response.append(result['__id'])
            while results:
                results = yield motor.Op(cursor.to_list, length=10)
                for result in results:
                    if '__id' in result:
                        response.append(result['__id'])

        else:
            if self.request.body:
                self.set_status(400)
                return

            response = yield motor.Op(self.collection.find_one,
                                      {'__id': identifier},
                                      {'_id': 0, '__id': 0})

            if keyword:
                # Return the whole document
                keys = keyword.split('/')
                while keys:
                    key = keys.pop(0)
                    if type(response) is dict:
                        response = response.get(key, {})

        if response is not None:
            self.set_header('Content-Type', 'application/json')
            self.write(json.dumps(response))
           #TODO: Add audit log: logging.info("User %s accessed password for device %s" % (self.user, identifier))
        else:
            self.set_status(404)

    @gen.coroutine
    def delete(self, identifier=None, keyword=None):
        """Delete a document or part of a document"""

        if not self.access == 'POST' and options.url:
            self.set_status(401)
            self.finish() 
            return

        if keyword:
            # Remove part of a document
            document = yield motor.Op(self.collection.find_one,
                                      {'__id': identifier})
            if document:
                print "found: %s" % document
                print "keyword: %s" % keyword

                keys = keyword.split('/')

                parent = None
                new = None
                while keys:
                    if new:
                        key = keys.pop(0)
                        if parent:
                            parent = parent[key]
                        else:
                            parent = document[key]
                    else:
                        new = keys.pop()

                if parent:
                    del parent[new]
                else:
                    del document[new]

                yield motor.Op(self.collection.save, document)

        elif identifier:
            # Remove the document
            yield motor.Op(self.collection.remove, {'__id': identifier})

        else:
            # Drop the collection
            yield motor.Op(self.collection.drop)

        self.set_status(204)

    @gen.coroutine
    def post(self, identifier=None, keyword=None):
        """Create a new document, collection or database"""

        if not self.access == 'POST' and options.url:
            self.set_status(401)
            self.finish() 
            return

        if identifier:
            document = yield motor.Op(self.collection.find_one,
                                      {'__id': identifier})

            if self.request.body:
                try:
                    data = json.loads(self.request.body)
                except:
                    self.set_status(400)
                    return
            else:
                data = {}

            if keyword:
                if document:
                    keys = keyword.split('/')

                    parent = None
                    new = None
                    while keys:
                        if new:
                            key = keys.pop(0)
                            if parent is not None:
                                try:
                                    parent = parent[key]
                                except KeyError:
                                    new = {key: new}
                            else:
                                if key not in document:
                                    document[key] = {}
                                parent = document[key]

                        else:
                            new = {keys.pop(): data}

                    try:
                        if parent is not None:
                            parent.update(new)
                        else:
                            document.update(new)

                    except AttributeError:
                        self.set_status(409)
                        return

                    yield motor.Op(self.collection.save, document)

                else:
                    # Create a new document
                    keys = keyword.split('/')

                    while keys:
                        key = keys.pop()
                        if document:
                            document = {key: document}
                        else:
                            document = {key: data}

                    document['__id'] = identifier
                    yield motor.Op(self.collection.save, document)

            else:
                try:
                    if document:
                        document.update(data)
                    else:
                        document = {'__id': identifier}
                        document.update(data)
                except ValueError:
                    self.set_status(400)
                    return

                yield motor.Op(self.collection.save, document)

            self.set_status(204)
            return

        else:
            self.set_status(400)
            return


def main():
    """Setup the application and start listening for traffic"""

    
    if options.logtype == 'logstash':
        logger = logging.getLogger()
        handler = logging.FileHandler(options.log)
        formatter = logstash_formatter.LogstashFormatter()

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    try:
        tornado.options.parse_command_line()
    except tornado.options.Error, exc:
        print(exc)
        return

    client = motor.MotorClient(options.mongodb).open_sync()
    database = client[options.database]
    application = tornado.web.Application([
        (r"/(.*?)/(.*)", PrefsHandler, dict(database=database)),
        (r"/(.*?)", PrefsHandler, dict(database=database)),
    ])

    print('Listening on http://0.0.0.0:%s' % options.port)
    application.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
