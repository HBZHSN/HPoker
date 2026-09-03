"""Shared test isolation for process-global poker services."""

import copy
import os

# Set this before importing the application modules.  Their module-level
# UserManager singleton must never open the production users file in pytest.
os.environ["USERS_DATA_FILE"] = ":memory:"

import pytest

from backend.app.models.user import User, hash_password
from backend.app.services.user_manager import UserManager, user_manager
from backend.app.services.room_manager import room_manager
from backend.app.services.balance_manager import balance_manager
from backend.app.services.timeout_manager import timeout_manager


PRODUCTION_USERS_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "users.json")
)
_real_save_to_storage = UserManager.save_to_storage


def _save_user_storage_outside_production_file(self):
    """Reject accidental test writes to the real users database."""
    storage_path = self.storage_path
    if (
        storage_path
        and storage_path != ":memory:"
        and os.path.abspath(storage_path) == PRODUCTION_USERS_PATH
    ):
        raise AssertionError("Tests must not write backend/data/users.json")
    _real_save_to_storage(self)


# Keep temporary user-storage tests possible while making the production path
# fail closed for every UserManager instance created during this test process.
UserManager.save_to_storage = _save_user_storage_outside_production_file


@pytest.fixture(autouse=True)
def isolate_persisted_storage():
    """Keep test data strictly isolated from production storage and real users.

    During tests, user_manager contains ONLY the three dedicated test accounts:
    test1, test2, and test3. No real accounts (admin, fwd, hx, yy) exist in memory.
    """
    original_room_path = room_manager.storage_path
    original_rooms = dict(room_manager._rooms)

    original_bal_path = balance_manager.storage_path
    original_bal_entries = copy.deepcopy(balance_manager._entries)
    original_bal_batches = copy.deepcopy(balance_manager._batches)

    original_user_path = user_manager.storage_path
    original_users = copy.deepcopy(user_manager._users)
    original_tokens = copy.deepcopy(user_manager._tokens)

    room_manager.storage_path = ":memory:"
    room_manager._rooms = {}

    balance_manager.storage_path = ":memory:"
    balance_manager._entries = {}
    balance_manager._batches = {}

    # Strictly isolate: Only test1, test2, test3 exist during test execution
    user_manager.storage_path = ":memory:"
    user_manager._users = {
        "u_test1": User(user_id="u_test1", username="test1", nickname="test1", avatar="🧪", is_admin=False, is_test=True, password_hash=hash_password("123")),
        "u_test2": User(user_id="u_test2", username="test2", nickname="test2", avatar="🧪", is_admin=False, is_test=True, password_hash=hash_password("123")),
        "u_test3": User(user_id="u_test3", username="test3", nickname="test3", avatar="🧪", is_admin=False, is_test=True, password_hash=hash_password("123")),
    }
    user_manager._tokens = {}

    yield

    for room_id in tuple(room_manager._rooms):
        timeout_manager.cancel_all_timers(room_id)

    room_manager._rooms = original_rooms
    room_manager.storage_path = original_room_path

    balance_manager.storage_path = original_bal_path
    balance_manager._entries = original_bal_entries
    balance_manager._batches = original_bal_batches

    user_manager.storage_path = original_user_path
    user_manager._users = original_users
    user_manager._tokens = original_tokens
