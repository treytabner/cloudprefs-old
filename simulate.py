"""Cloud Preferences simulation tool"""

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

import datetime
import json
import os
import random
import requests
import string
import time
import uuid

from multiprocessing import Process


ENDPOINT = os.environ.get('ENDPOINT', 'http://localhost:8888')
START = int(os.environ.get('START', 100000))
MAX = int(os.environ.get('MAX', 1000))  # Simulate 1000 users at once


def random_password(size=12, chars=string.letters + string.digits):
    return ''.join(random.choice(chars) for x in range(size))


def headers(user_id):
    return {
        'X-User-Id': str(START),
        #'X-User-Id': str(user_id),
    }


def get(user_id, url):
    return requests.get('%s/%s' % (ENDPOINT, url),
                        headers=headers(user_id))


def post(user_id, url, payload=None):
    if payload:
        data = json.dumps(payload)
    else:
        data = None

    return requests.post('%s/%s' % (ENDPOINT, url), data=data,
                         headers=headers(user_id))


def delete(user_id, url):
    return requests.delete('%s/%s' % (ENDPOINT, url),
                           headers=headers(user_id))


def simulate(user_id):
    #response = delete(user_id, '')
    #assert response.status_code == 204

    #response = post(user_id,
    #                'managed_cloud/build_config',
    #                payload=['driveclient', 'monitoring'])
    #assert response.status_code == 204

    #response = get(user_id, 'managed_cloud/build_config')
    #assert response.status_code == 200
    #assert 'driveclient' in response.json()
    #assert 'monitoring' in response.json()

    devices = [uuid.uuid4() for x in range(int(os.environ.get('DEVICES', 10)))]
    for device in devices:
        current = random_password()
        updated = int(time.time())
        payload = {
            "current": current,
            "updated": updated,
        }
        response = post(user_id, '%s/password' % device,
                        payload=payload)
        assert response.status_code == 204

        #response = get(user_id, '%s/password' % device)
        #assert response.status_code == 200
        #assert payload == response.json()


def main():
    start = datetime.datetime.now()
    tenants = range(START, START+MAX)
    sims = []
    for tenant in tenants:
        p = Process(target=simulate, args=(tenant,))
        p.start()
        sims.append(p)

    while sims:
        print "Sims: %s" % len(sims)

        for sim in sims:
            if not sim.is_alive():
                sims.remove(sim)

        time.sleep(0.1)

    end = datetime.datetime.now()
    print "Total: %s" % (end - start)


if __name__ == "__main__":
    main()
