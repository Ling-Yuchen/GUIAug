from app.services.image_service import ImageService
from app.services.device_service import DeviceService
from app.services.implements.device_service_impl_adb import ADBDeviceServiceImpl
from app.services.implements.script_service_impl_adb import AndroidScriptServiceImpl
from app.services.mutation_service import MutationService
from app.services.script_service import ScriptService
from app.services.implements.image_service_impl import ImageServiceImpl
# from app.services.implements.device_service_impl_hdc import HarmonyDeviceServiceImpl
# from app.services.implements.script_service_impl_hdc import HarmonyScriptServiceImpl
from app.services.implements.mutation_service_impl_adb import MutationServiceImpl


img_service = ImageServiceImpl()
# device_service = HarmonyDeviceServiceImpl()
device_service = ADBDeviceServiceImpl()
# script_service = HarmonyScriptServiceImpl()
script_service = AndroidScriptServiceImpl()
mutation_service = MutationServiceImpl()


def get_image_service() -> ImageService:
    return img_service

def get_device_service() -> DeviceService:
    return device_service

def get_script_service() -> ScriptService:
    return script_service

def get_mutation_service() -> MutationService:
    return mutation_service
