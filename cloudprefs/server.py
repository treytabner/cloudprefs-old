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

import motor

import tornado.ioloop
import tornado.web

from tornado import gen


class PrefsHandler(tornado.web.RequestHandler):
    @gen.coroutine
    def initialize(self, client):
        """Verify authentication and setup database access"""
        tenant_id = self.request.headers.get('X-Tenant-Id')
        self.db = client[tenant_id]

    @gen.coroutine
    def get(self, category=None, identifier=None, keyword=None):
        """Return a document or part of a document for specified entity"""
        results = None
        response = None

        if not category:
            # List all collections
            collections = yield motor.Op(self.db.collection_names)
            try:
                collections.remove('system.indexes')
            except:
                pass
            response = dict(categories=collections)

        elif not identifier:
            # List all documents
            collection = self.db[category]
            cursor = collection.find({}, {'_id': 0, 'id': 1})
            ids = []
            results = yield motor.Op(cursor.to_list, length=10)
            for result in results:
                ids.append(result['id'])
            while results:
                results = yield motor.Op(cursor.to_list, length=10)
                for result in results:
                    ids.append(result['id'])

            response = {category: ids}

        else:
            collection = self.db[category]
            result = yield motor.Op(collection.find_one, {'id': identifier}, {'_id': 0})

            if keyword:
                # Return the whole document
                keys = keyword.split('/')
                while keys:
                    key = keys.pop(0)
                    result = result.get(key, {})

                response = {keyword: result}
            else:
                # Print just what was asked for
                response = result

        if response:
            self.write(response)
        else:
            self.set_status(404)


def main():
    client = motor.MotorClient().open_sync()
    application = tornado.web.Application([
        (r"/(.*?)/(.*?)/(.*)", PrefsHandler, dict(client=client)),
        (r"/(.*?)/(.*?)", PrefsHandler, dict(client=client)),
        (r"/(.*?)", PrefsHandler, dict(client=client)),
    ])
    print 'Listening on http://localhost:8888'
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
