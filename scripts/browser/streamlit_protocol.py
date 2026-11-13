"""Describe the lifecycle fields of the installed Streamlit wire protocol."""
from __future__ import annotations

import json
from importlib.metadata import version

from google.protobuf.descriptor import FieldDescriptor
from streamlit.proto import BackMsg_pb2, ClientState_pb2, Common_pb2, WidgetStates_pb2
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg, ForwardMsgMetadata


def describe() -> dict:
    run = ForwardMsgMetadata.DESCRIPTOR.fields_by_name["run"].message_type
    selected = [
        (ForwardMsg.DESCRIPTOR, ("metadata", "new_session", "script_finished")),
        (ForwardMsgMetadata.DESCRIPTOR, ("run",)),
        (run, ("script_run_id", "fragment_ids")),
        (BackMsg_pb2.BackMsg.DESCRIPTOR, ("rerun_script",)),
        (ClientState_pb2.ClientState.DESCRIPTOR, ("widget_states", "fragment_id")),
        (WidgetStates_pb2.WidgetStates.DESCRIPTOR, ("widgets",)),
        (WidgetStates_pb2.WidgetState.DESCRIPTOR, ("file_uploader_state_value",)),
        (Common_pb2.FileUploaderState.DESCRIPTOR, ("uploaded_file_info",)),
        (Common_pb2.UploadedFileInfo.DESCRIPTOR, ("file_id",)),
    ]
    nested = {}
    for descriptor, names in selected:
        fields = {}
        for name in names:
            field = descriptor.fields_by_name[name]
            if name == "new_session":
                # Presence is enough; the run identity lives in metadata.
                kind = "bytes"
            elif field.message_type is not None:
                kind = field.message_type.name
            elif field.type == FieldDescriptor.TYPE_ENUM:
                kind = "uint32"
            else:
                assert field.type == FieldDescriptor.TYPE_STRING
                kind = "string"
            fields[name] = {"id": field.number, "type": kind}
            if field.is_repeated:
                fields[name]["rule"] = "repeated"
        nested[descriptor.name] = {"fields": fields}
    return {"streamlit_version": version("streamlit"), "schema": {"nested": nested}}


if __name__ == "__main__":
    print(json.dumps(describe()))
