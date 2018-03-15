import pytest


def pytest_addoption(parser):
    parser.addoption("--rustvm_location", action="store",
                     default="/home/ben/dev/vm-rust/target/release/vm-rust",
                     help="location of vm binary")


@pytest.fixture
def binloc(request):
    return request.config.getoption("--rustvm_location")

