"""Client options must not override what the connection string sets."""

from database import MONGO_OPTIONS, client_options

COSMOS_URI = (
    "mongodb+srv://airyatra_app:pw@mongo-airyatra-dev.global.mongocluster.cosmos.azure.com/"
    "?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"
)


def test_cosmos_uri_keeps_its_own_retrywrites_and_idle_time():
    options = client_options(COSMOS_URI)

    assert "retryWrites" not in options
    assert "maxIdleTimeMS" not in options
    assert options["w"] == "majority"
    assert options["maxPoolSize"] == MONGO_OPTIONS["maxPoolSize"]


def test_plain_uri_gets_every_default():
    assert client_options("mongodb+srv://u:p@cluster.mongodb.net/") == MONGO_OPTIONS
    assert client_options("mongodb://localhost:27017") == MONGO_OPTIONS
