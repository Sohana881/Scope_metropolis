
import pytest

from services.database import clear_all_data


@pytest.fixture(autouse=True)
def clean_database_between_tests():
    clear_all_data()
    yield
    clear_all_data()
