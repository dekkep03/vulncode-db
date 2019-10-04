# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import datetime
import os

import cfg
from data.database import DEFAULT_DATABASE
from flask_migrate import upgrade as alembic_upgrade
from lib.app_factory import create_app
from data.models.vulnerability import Vulnerability
from data.models.vulnerability import VulnerabilityGitCommits
from data.models.vulnerability import VulnerabilityResources
from data.models.nvd import Cpe
from data.models.nvd import Nvd
from data.models.nvd import Reference
import pytest


DOCKER_DB_URI = 'mysql+mysqldb://root:test_db_pass@tests-db:3306/main'
TEST_CONFIG = {
    'TESTING': True,
    'WTF_CSRF_ENABLED': False,
    'DEBUG': True,
    'SQLALCHEMY_DATABASE_URI': DOCKER_DB_URI,
    'SQLALCHEMY_ENGINE_OPTIONS': {
        'echo': True,  # log queries
        # 'echo_pool': True,  # log connections
    }
}


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test to run only in integration tests"
    )


@pytest.fixture(scope='session')
def app():
    app = create_app(TEST_CONFIG)
    # Establish an application context before running the tests.
    ctx = app.app_context()
    ctx.push()
    yield app
    ctx.pop()


@pytest.fixture
def client(app, request, db_session):
    with app.test_client() as c:
        yield c


@pytest.fixture(scope="session")
def _db(app):
    """Returns session-wide initialised database."""
    db = DEFAULT_DATABASE.db

    # setup databases and tables
    with open(os.path.join(cfg.BASE_DIR, 'docker/db_schema.sql'), 'rb') as f:
        create_schemas_sql = f.read().decode('utf8')

    with app.app_context():
        # clear database
        db.drop_all()
        db.engine.execute('DROP TABLE IF EXISTS alembic_version')

        # build database
        db.engine.execute(create_schemas_sql)
        alembic_upgrade()

        # create data
        vuln_cves = list('CVE-1970-{}'.format(1000+i) for i in range(10))
        new_cves = list('CVE-1970-{}'.format(2000+i) for i in range(10))
        cves = vuln_cves + new_cves
        session = db.session

        nvds = []
        for i, cve in enumerate(cves, 1):
            nvds.append(Nvd(
                cve_id=cve,
                descriptions=[],
                references=[
                    Reference(
                        link='https://cve.mitre.org/cgi-bin/cvename.cgi?name={}'.format(cve),
                        source='cve.mitre.org',
                    ),
                ],
                published_date=datetime.date.today(),
                cpes=[
                    Cpe(
                        vendor='Vendor {}'.format(i),
                        product='Product {}'.format(j),
                    )
                    for j in range(1, 4)
                ]
            ))
        session.add_all(nvds)

        vulns = []
        for i, cve in enumerate(vuln_cves, 1):
            repo_owner = 'OWNER'
            repo_name = 'REPO{i}'.format(i=i)
            repo_url = 'https://github.com/{owner}/{repo}/'.format(
                owner=repo_owner,
                repo=repo_name,
            )
            commit = '{:07x}'.format(0x1234567 + i)
            vulns.append(Vulnerability(
                cve_id=cve,
                date_created=datetime.date.today(),
                comment='Vulnerability {} comment'.format(i),
                commits=[
                    VulnerabilityGitCommits(
                        commit_link='{repo_url}commit/{commit}'.format(
                            repo_url=repo_url, commit=commit,
                        ),
                        repo_owner=repo_owner,
                        repo_name=repo_name,
                        # repo_url=repo_url,
                        commit_hash=commit
                    )
                ]
            ))
        session.add_all(vulns)
        session.commit()
    return db
