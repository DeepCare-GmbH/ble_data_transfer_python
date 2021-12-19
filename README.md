# bluetooth_data_transfer_python

Source of the proto files: [dart repository](https://github.com/DeepCare-GmbH/ble_data_transfer_dart/tree/develop/proto)

## generate Python files

### Google protoc

```bash
cd proto
protoc --python_out=../gen messages.proto
protoc --python_out=../gen transfer_data.proto
```

### Bettercode protoc

```bash
protoc --python_betterproto_out=gen proto/transfer_data.proto
```
