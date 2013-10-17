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
        collection = headers.get('X-Project-Id', headers.get('X-Tenant-Id'))
        self.collection = database[collection]

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
            cursor = self.collection.find({}, {'_id': 0, '__id': 1})
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
            response = yield motor.Op(self.collection.find_one,
                                      {'__id': identifier})
            if response:
                del response[keyword]
                yield motor.Op(self.collection.save, response)

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

            try:
                data = json.loads(self.request.body)
            except:
                self.set_status(400)
                return

            if keyword:
                if document:
                    keys = keyword.split('/')

                    new = None
                    while keys:
                        key = keys.pop()
                        if new:
                            new = {key: new}
                        else:
                            new = {key: data}

                    document.update(new)

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

        else:
            self.set_status(400)
            return


def main():
    """Setup the application and start listening for traffic"""
    try:
        tornado.options.parse_command_line()
    except tornado.options.Error, e:
        print(e)
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
