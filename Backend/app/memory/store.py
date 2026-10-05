"""DynamoDB persistence. Single-table design:

    pk = "SESSION#<session_id>"
    sk = "META"            session metadata (case file, memory config, game state)
    sk = "MSG#<000123>"    one item per message, sorted by sequence number

Message ids are the zero-padded sequence number, so pk + "MSG#" + id addresses
any message directly. Sequence numbers come from an atomic counter on META.
"""
from __future__ import annotations

import time
import uuid
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key

from app.config import Settings


def _clean(value: Any) -> Any:
    """Convert DynamoDB Decimals back to int/float, recursively."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_clean(v) for v in value]
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    return value


def _dynamo(value: Any) -> Any:
    """DynamoDB rejects Python floats; store them as Decimal."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_dynamo(v) for v in value]
    if isinstance(value, dict):
        return {k: _dynamo(v) for k, v in value.items()}
    return value


def _pk(session_id: str) -> str:
    return f"SESSION#{session_id}"


def _public(item: dict) -> dict:
    return {k: v for k, v in _clean(item).items() if k not in ("pk", "sk")}


class SessionStore:
    def __init__(self, settings: Settings):
        kwargs: dict[str, Any] = {"region_name": settings.aws_region}
        if settings.dynamodb_endpoint_url:
            kwargs["endpoint_url"] = settings.dynamodb_endpoint_url
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        self.ddb = boto3.resource("dynamodb", **kwargs)
        self.table_name = settings.dynamodb_table
        if settings.auto_create_table:
            self.ensure_table()
        self.table = self.ddb.Table(self.table_name)

    def ensure_table(self) -> None:
        client = self.ddb.meta.client
        try:
            client.describe_table(TableName=self.table_name)
        except client.exceptions.ResourceNotFoundException:
            self.ddb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {"AttributeName": "pk", "KeyType": "HASH"},
                    {"AttributeName": "sk", "KeyType": "RANGE"},
                ],
                AttributeDefinitions=[
                    {"AttributeName": "pk", "AttributeType": "S"},
                    {"AttributeName": "sk", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            client.get_waiter("table_exists").wait(TableName=self.table_name)

    # ---- sessions -------------------------------------------------------

    def create_session(self, fields: dict) -> dict:
        session_id = uuid.uuid4().hex[:12]
        item = {
            "pk": _pk(session_id),
            "sk": "META",
            "session_id": session_id,
            "created_at": int(time.time()),
            "msg_count": 0,
            **fields,
        }
        self.table.put_item(Item=_dynamo(item))
        return _public(item)

    def get_session(self, session_id: str) -> dict | None:
        res = self.table.get_item(Key={"pk": _pk(session_id), "sk": "META"})
        return _public(res["Item"]) if "Item" in res else None

    def update_session(self, session_id: str, **fields: Any) -> dict:
        names = {f"#{k}": k for k in fields}
        values = {f":{k}": _dynamo(v) for k, v in fields.items()}
        expr = "SET " + ", ".join(f"#{k} = :{k}" for k in fields)
        res = self.table.update_item(
            Key={"pk": _pk(session_id), "sk": "META"},
            UpdateExpression=expr,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
        return _public(res["Attributes"])

    def list_sessions(self, limit: int = 50) -> list[dict]:
        # A scan is fine at demo scale; add a GSI on created_at for production.
        items: list[dict] = []
        kwargs: dict[str, Any] = {"FilterExpression": Attr("sk").eq("META")}
        while True:
            res = self.table.scan(**kwargs)
            items.extend(res.get("Items", []))
            if "LastEvaluatedKey" not in res or len(items) >= limit:
                break
            kwargs["ExclusiveStartKey"] = res["LastEvaluatedKey"]
        sessions = [_public(i) for i in items]
        sessions.sort(key=lambda s: s.get("created_at", 0), reverse=True)
        return sessions[:limit]

    # ---- messages -------------------------------------------------------

    def _next_seq(self, session_id: str) -> int:
        res = self.table.update_item(
            Key={"pk": _pk(session_id), "sk": "META"},
            UpdateExpression="ADD msg_count :one",
            ExpressionAttributeValues={":one": 1},
            ReturnValues="UPDATED_NEW",
        )
        return int(res["Attributes"]["msg_count"])

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tokens: int,
        pinned: bool = False,
        extra: dict | None = None,
    ) -> dict:
        msg_id = f"{self._next_seq(session_id):06d}"
        item = {
            "pk": _pk(session_id),
            "sk": f"MSG#{msg_id}",
            "id": msg_id,
            "role": role,
            "content": content,
            "tokens": tokens,
            "pinned": pinned,
            "archived": False,
            "created_at": int(time.time()),
            **(extra or {}),
        }
        self.table.put_item(Item=_dynamo(item))
        return _public(item)

    def list_messages(self, session_id: str) -> list[dict]:
        items: list[dict] = []
        kwargs: dict[str, Any] = {
            "KeyConditionExpression": Key("pk").eq(_pk(session_id)) & Key("sk").begins_with("MSG#")
        }
        while True:
            res = self.table.query(**kwargs)
            items.extend(res.get("Items", []))
            if "LastEvaluatedKey" not in res:
                break
            kwargs["ExclusiveStartKey"] = res["LastEvaluatedKey"]
        return [_public(i) for i in items]

    def set_pinned(self, session_id: str, msg_id: str, pinned: bool) -> dict:
        res = self.table.update_item(
            Key={"pk": _pk(session_id), "sk": f"MSG#{msg_id}"},
            UpdateExpression="SET pinned = :p",
            ConditionExpression=Attr("pk").exists(),
            ExpressionAttributeValues={":p": pinned},
            ReturnValues="ALL_NEW",
        )
        return _public(res["Attributes"])

    def mark_archived(self, session_id: str, msg_ids: list[str]) -> None:
        for msg_id in msg_ids:
            self.table.update_item(
                Key={"pk": _pk(session_id), "sk": f"MSG#{msg_id}"},
                UpdateExpression="SET archived = :t",
                ExpressionAttributeValues={":t": True},
            )
