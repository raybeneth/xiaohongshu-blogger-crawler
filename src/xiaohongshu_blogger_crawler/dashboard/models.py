from __future__ import annotations

from datetime import datetime
from enum import IntEnum

from pydantic import BaseModel, Field


class SubscriptionStatus(IntEnum):
    WAIT_ACTIVATE = 1
    WAIT_INIT = 2
    INITIALIZING = 3
    SUBSCRIBING = 4
    INIT_ABORT = 10
    TERMINATED = 11
    EXPIRED = 12


SUBSCRIPTION_STATUS_LABEL: dict[int, str] = {
    1: "待激活",
    2: "待初始化",
    3: "初始化中",
    4: "订阅中",
    10: "初始化异常终止",
    11: "订阅终止",
    12: "订阅到期",
}

XHS_REGISTER_STATUS_LABEL: dict[int, str] = {
    0: "等待注册",
    1: "注册成功",
    999: "异常",
}


class BrandSubscription(BaseModel):
    id: int = Field(description="主键")
    state: int = Field(description="数据状态（0=无效；1=有效）")
    group_id: int = Field(description="集团ID")
    brand_id: int = Field(description="品牌ID")
    contract_code: str = Field(description="合约标识")
    counselor: str | None = Field(default=None, description="顾问")
    versions: int = Field(description="合约版本（0=年费；1=报告）")
    status: int = Field(description="订阅状态")
    contract_start_time: datetime = Field(description="合约开始时间")
    contract_end_time: datetime = Field(description="合约结束时间")
    data_start_time: datetime = Field(description="数据起始时间")
    data_end_time: datetime = Field(description="数据结束时间")
    sampling_proportion: int = Field(description="抽样比例(%)")
    xhs_register_status: int = Field(description="小红书注册状态")
    create_time: datetime | None = Field(default=None, description="创建时间")
    update_time: datetime | None = Field(default=None, description="更新时间")

    @property
    def status_label(self) -> str:
        return SUBSCRIPTION_STATUS_LABEL.get(self.status, f"未知({self.status})")

    @property
    def xhs_register_label(self) -> str:
        return XHS_REGISTER_STATUS_LABEL.get(self.xhs_register_status, f"未知({self.xhs_register_status})")

    @property
    def versions_label(self) -> str:
        return "年费版本" if self.versions == 0 else "报告版本"
