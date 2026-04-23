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
    brand_name: str | None = Field(default=None, description="品牌名称（来自 brand_ext）")
    doris_url: str | None = Field(default=None, description="Doris连接地址")
    doris_account: str | None = Field(default=None, description="Doris连接账号")
    doris_password: str | None = Field(default=None, description="Doris连接密码（密文）")

    @property
    def status_label(self) -> str:
        return SUBSCRIPTION_STATUS_LABEL.get(self.status, f"未知({self.status})")

    @property
    def xhs_register_label(self) -> str:
        return XHS_REGISTER_STATUS_LABEL.get(self.xhs_register_status, f"未知({self.xhs_register_status})")

    @property
    def versions_label(self) -> str:
        return "年费版本" if self.versions == 0 else "报告版本"


SYS_CONFIG_TYPE_LABEL: dict[int, str] = {
    0: "系统基础配置",
    1: "运维系统配置",
    2: "业务必须配置",
    3: "非必须配置",
}


class SysConfig(BaseModel):
    id: int = Field(description="主键ID")
    state: int = Field(description="状态: 0无效、1有效")
    create_time: datetime | None = Field(default=None, description="创建时间")
    update_time: datetime | None = Field(default=None, description="更新时间")
    code: str = Field(description="配置项唯一编码")
    value: str = Field(description="配置值")
    type: int = Field(default=0, description="配置类型")
    remark: str | None = Field(default=None, description="配置说明")


CLEAN_TASK_STATUS_LABEL: dict[int, str] = {
    0: "待执行",
    1: "执行中",
    2: "成功",
    3: "失败",
    9: "等待依赖服务执行",
}


class CleanTaskProgress(BaseModel):
    id: int = Field(description="主键")
    state: int = Field(description="状态")
    create_time: datetime | None = Field(default=None, description="创建时间")
    update_time: datetime | None = Field(default=None, description="更新时间")
    code: str = Field(description="任务标识")
    group_id: int = Field(description="公司ID")
    brand_id: int = Field(description="品牌ID")
    status: int = Field(description="执行状态")
    progress: datetime | None = Field(default=None, description="执行进度")
    fail_cause: str | None = Field(default=None, description="失败原因")
    brand_name: str | None = Field(default=None, description="品牌名称")
