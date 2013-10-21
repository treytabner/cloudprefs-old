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

import tornado.ioloop
import tornado.web

from tornado import gen
from tornado.options import define, options


define("port", default="8888", help="Port to listen on")
define("mongodb", default="127.0.0.1:27017", help="MongoDB host or hosts")
define("database", default="cloudprefs", help="Database name")


class PrefsHandler(tornado.web.RequestHandler):
    """Cloud Preferences Request Handler"""

    @gen.coroutine
    def initialize(self, database):
        """Verify authentication and setup database access"""
        headers = self.request.headers
        self.tenant_id = headers.get('X-Tenant-Id')
        self.collection = database[self.tenant_id]

    @gen.coroutine
    def prepare(self):
        """Make sure we have a valid collection to work with"""
        if 'collection' not in dir(self):
            self.set_status(401)
            self.finish()

    @gen.coroutine
    def get(self, identifier=None, keyword=None):
        """Return a document or part of a document for specified entity"""
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
        else:
            self.set_status(404)

    @gen.coroutine
    def delete(self, identifier=None, keyword=None):
        """Delete a document or part of a document"""
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

    @gen.coroutine
    def post(self, identifier=None, keyword=None):
        """Create a new document, collection or database"""
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
