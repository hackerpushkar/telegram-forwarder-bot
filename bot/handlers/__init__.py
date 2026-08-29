from aiogram import Router
from .common import router as common_router
from .routes_manager import router as routes_router
from .settings_handler import router as settings_router
from .userbot_manager import router as userbot_router
from .forwarder import router as forwarder_router

def get_main_router() -> Router:
    main_router = Router()
    # Order: common -> userbot -> routes -> settings -> forwarder
    main_router.include_router(common_router)
    main_router.include_router(userbot_router)
    main_router.include_router(routes_router)
    main_router.include_router(settings_router)
    main_router.include_router(forwarder_router)
    return main_router
