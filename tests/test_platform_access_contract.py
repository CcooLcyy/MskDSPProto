"""实际编译管理协议，验证平台出厂配置线格式及既有接口兼容性。"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory


ROOT = Path(__file__).resolve().parents[1]


class PlatformAccessContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as temporary:
            descriptor = Path(temporary) / "module-manager.pb"
            subprocess.run([shutil.which("protoc") or "protoc", "--proto_path=.",
                            f"--descriptor_set_out={descriptor}", "ModuleManager.proto"],
                           cwd=ROOT, check=True, capture_output=True)
            cls.file = descriptor_pb2.FileDescriptorSet.FromString(descriptor.read_bytes()).file[0]
        cls.pool = descriptor_pool.DescriptorPool()
        cls.pool.Add(cls.file)

    def message(self, name):
        return message_factory.GetMessageClass(self.pool.FindMessageTypeByName("ModuleManagerProto." + name))

    # 旧 RPC 保留原顺序，新增配置接口追加，避免影响既有客户端及生成桩布局。
    def test_existing_methods_are_preserved_and_new_unary_methods_are_appended(self):
        service, = self.file.service
        self.assertEqual([method.name for method in service.method], [
            "GetModuleInfo", "GetRunningModuleInfo", "StartModule", "StopModule", "UploadModule",
            "DeleteModule", "SaveModuleStartConfig", "GetPlatformAccessConfig", "SetPlatformAccessConfig",
        ])
        for method in service.method[-2:]:
            self.assertFalse(method.client_streaming)
            self.assertFalse(method.server_streaming)
            self.assertEqual(method.output_type, ".ModuleManagerProto.PlatformAccessStatus")

    # 读取状态只暴露令牌是否存在，不提供可还原令牌字段。
    def test_read_status_has_fixed_numbers_and_no_secret_field(self):
        fields = self.message("PlatformAccessStatus").DESCRIPTOR.fields
        self.assertEqual({field.name: field.number for field in fields}, {
            "enabled": 1, "platform_target": 2, "device_id": 3, "token_configured": 4,
            "ssh_enabled": 5, "ssh_port": 6, "revision": 7, "online": 8, "last_error": 9,
        })
        self.assertNotIn("device_token", {field.name for field in fields})

    # 保存只接受身份与开关，地址由设备固定，令牌更新和显式清除可区分。
    def test_write_contract_has_revision_and_clear_semantics_without_target(self):
        fields = self.message("SetPlatformAccessConfigRequest").DESCRIPTOR.fields
        self.assertEqual({field.name: field.number for field in fields}, {
            "expected_revision": 1, "enabled": 2, "device_id": 3, "device_token": 4,
            "ssh_enabled": 5, "ssh_port": 6, "clear_device_token": 7,
        })
        self.assertNotIn("platform_target", {field.name for field in fields})

    # 保留令牌的配置写入使用稳定线格式，不把脱敏状态误写成令牌。
    def test_write_request_golden_wire_preserves_empty_token(self):
        request = self.message("SetPlatformAccessConfigRequest")(
            expected_revision=1, enabled=True, device_id="a", ssh_enabled=True, ssh_port=22)
        self.assertEqual(request.SerializeToString(), bytes.fromhex("080110011a016128013016"))
        decoded = type(request).FromString(bytes.fromhex("080110011a016128013016"))
        self.assertEqual(decoded.device_token, "")
        self.assertFalse(decoded.clear_device_token)

    # 显式清除与空值保留在网络上不同，设备可阻止误删现有凭据。
    def test_explicit_token_clear_has_distinct_wire_value(self):
        request = self.message("SetPlatformAccessConfigRequest")(clear_device_token=True)
        self.assertEqual(request.SerializeToString(), bytes.fromhex("3801"))


if __name__ == "__main__":
    unittest.main()
