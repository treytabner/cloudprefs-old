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

from pymongo.errors import CollectionInvalid


define("port", default="8888", help="Port to listen on")
define("mongodb", default="127.0.0.1:27017", help="MongoDB host or hosts")


class PrefsHandler(tornado.web.RequestHandler):
    """Cloud Preferences Request Handler"""

    @gen.coroutine
    def initialize(self, client):
        """Verify authentication and setup database access"""
        self.tenant_id = self.request.headers.get('X-Tenant-Id')
        self.client = client
        self.database = self.client[self.tenant_id]

    @gen.coroutine
    def prepare(self):
        """Make sure we have a valid database"""
        if not self.tenant_id or not self.database:
            self.set_status(401)
            self.finish()

    @gen.coroutine
    def get(self, category=None, identifier=None, keyword=None):
        """Return a document or part of a document for specified entity"""
        response = None

        if not category:
            # List all collections
            response = yield motor.Op(self.database.collection_names)
            if 'system.indexes' in response:
                response.remove('system.indexes')

        elif not identifier:
            # List all documents
            collection = self.database[category]
            cursor = collection.find({}, {'_id': 0, '__id': 1})
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
            collection = self.database[category]
            response = yield motor.Op(collection.find_one,
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
    def delete(self, category=None, identifier=None, keyword=None):
        """Delete a collection, document or part of a document"""
        if category:
            collection = self.database[category]

            if keyword:
                # Remove part of a document
                response = yield motor.Op(collection.find_one,
                                          {'__id': identifier})
                if response:
                    del response[keyword]
                    yield motor.Op(collection.save, response)

            elif identifier:
                # Remove the document
                yield motor.Op(collection.remove, {'__id': identifier})

            else:
                # Drop the collection
                yield motor.Op(collection.drop)

        else:
            yield motor.Op(self.client.drop_database, self.tenant_id)

    @gen.coroutine
    def post(self, category=None, identifier=None, keyword=None):
        """Create a new document, collection or database"""
        if category:
            collection = self.database[category]

            if identifier:
                collection = self.database[category]

                document = yield motor.Op(collection.find_one,
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

                        yield motor.Op(collection.save, document)

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
                        yield motor.Op(collection.save, document)

                else:
                    if document:
                        document.update(data)
                    else:
                        document = {'__id': identifier}
                        document.update(data)

                    yield motor.Op(collection.save, document)

            else:
                # Create the specified collection
                try:
                    yield motor.Op(self.database.create_collection, category)

                    # And return a list of all collections
                    response = yield motor.Op(self.database.collection_names)
                    if 'system.indexes' in response:
                        response.remove('system.indexes')

                except CollectionInvalid:
                    self.set_status(409)


def main():
    """Setup the application and start listening for traffic"""
    try:
        tornado.options.parse_command_line()
    except tornado.options.Error, e:
        print(e)
        return

    client = motor.MotorClient(options.mongodb).open_sync()
    application = tornado.web.Application([
        (r"/(.*?)/(.*?)/(.*)", PrefsHandler, dict(client=client)),
        (r"/(.*?)/(.*?)", PrefsHandler, dict(client=client)),
        (r"/(.*?)", PrefsHandler, dict(client=client)),
    ])

    print('Listening on http://localhost:%s' % options.port)
    application.listen(options.port)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
