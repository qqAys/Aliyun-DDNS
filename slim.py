# -*- coding: utf-8 -*-
#  Copyright (c) 2021 - 2024 qqAys.

# @Time          : 2024/05/28 22:01
# @Author        : Jinx
# @Email-Private : me@qqays.xyz
# @Github        : https://github.com/qqAys/Aliyun-DDNS
# @File          : slim.py
# @Description   : 阿里云单记录DDNS脚本, slim版本模拟了阿里SDK请求, 无外部Python库依赖。所需环境: 公网IP网络环境、Python3

import binascii
import configparser
import datetime
import hashlib
import hmac
import json
import os
import platform
import re
import smtplib
import socket
import ssl
import sys
import time
import urllib.request
import uuid
from email.header import Header
from email.mime.text import MIMEText
from typing import Any
from urllib.parse import quote

# dns action
UPDATE = "update"
DESCRIBE = "describe"

# msg level
INFO = "INFO"
ERROR = "ERROR"


class Request:
    """阿里SDK请求模型"""

    def __init__(self):
        self.query = {}
        self.protocol = "HTTPS"
        self.port = 80
        self.method = "POST"
        self.headers = {}
        self.pathname = "/"
        self.body = None


class Utils:
    # 不可更改, 阿里验签用
    acs_version = "2015-01-09"
    tea_version = "0.3.0"
    signature_algorithm = "ACS3-HMAC-SHA256"

    def printer(self, level, *msg):
        print(
            f"{self.get_timestamp()} [{level}] {' '.join(self.to_str(m) for m in msg)}"
        )

    @staticmethod
    def get_unix_time() -> int:
        """获取 unix time"""
        return int(time.time())

    def get_timestamp(self, utc=False) -> str:
        """获取可读时间"""
        if utc:  # UTC时间为阿里验签用
            try:
                return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            except Exception as GetUtcTimeError:
                self.printer(INFO, "获取UTC方法错误, 尝试其他方法", GetUtcTimeError)
                return datetime.datetime.now(datetime.UTC).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                )
        else:  # 日志用
            return time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(self.get_unix_time())
            )

    def get_agent(self) -> str:
        """构造请求 user-agent , 阿里验签用"""
        return (
            f"AlibabaCloud ({platform.system()}; {platform.machine()}) "
            f"Python/{platform.python_version()} Core/{self.tea_version} TeaDSL/1"
        )

    @staticmethod
    def get_nonce() -> str:
        """构造标识符, 阿里验签用"""
        name = socket.gethostname() + str(uuid.uuid1())
        namespace = uuid.NAMESPACE_URL
        return str(uuid.uuid5(namespace, name))

    @staticmethod
    def hex_encode(raw) -> str:
        """十六进制编码"""
        return binascii.b2a_hex(raw).decode("utf-8")

    def hash_bytes(self, raw, sign_type) -> bytes:
        """哈希运算, 默认使用 ACS3-HMAC-SHA256"""
        if sign_type == "ACS3-HMAC-SHA256":
            return hashlib.sha256(raw).digest()
        else:
            self.printer(ERROR, "不支持的签名类型:", sign_type)
            sys.exit()

    @staticmethod
    def get_canonical_query_string(query) -> str:
        """规范化查询字符串"""
        canon_keys = []
        for k, v in query.items():
            if v is not None:
                canon_keys.append(k)

        canon_keys.sort()
        query_string = ""
        for key in canon_keys:
            value = quote(query[key], safe="~", encoding="utf-8")  # 进行URL编码
            if value is None:
                s = f"{key}&"
            else:
                s = f"{key}={value}&"
            query_string += s
        return query_string[:-1]

    def handle_headers(
        self, _headers, canonicalized=True
    ) -> Any:
        """处理请求头"""
        canon_keys = []
        tmp_headers = {}
        for k, v in _headers.items():
            if v is not None:
                if k.lower() not in canon_keys:
                    canon_keys.append(k.lower())
                    tmp_headers[k.lower()] = [self.to_str(v).strip()]
                else:
                    tmp_headers[k.lower()].append(self.to_str(v).strip())

        canon_keys.sort()
        if canonicalized is False:
            return {key: ",".join(sorted(tmp_headers[key])) for key in canon_keys}
        else:
            canonical_headers = ""
            for key in canon_keys:
                header_entry = ",".join(sorted(tmp_headers[key]))
                s = f"{key}:{header_entry}\n"
                canonical_headers += s
            return canonical_headers, ";".join(canon_keys)

    @staticmethod
    def to_str(val) -> Any:
        """转换字符串"""
        if val is None:
            return val

        if isinstance(val, bytes):
            return str(val, encoding="utf-8")
        else:
            return str(val)

    def signature_method(self, secret, source, sign_type) -> bytes:
        """加签, 默认使用 ACS3-HMAC-SHA256"""
        source = source.encode("utf-8")
        secret = secret.encode("utf-8")
        if sign_type == "ACS3-HMAC-SHA256":
            return hmac.new(secret, source, hashlib.sha256).digest()
        else:
            self.printer(ERROR, "不支持的签名类型:", sign_type)
            sys.exit()

    def get_authorization(self, _request, sign_type, payload, ak, secret) -> str:
        """构建授权"""
        canonicalized_query = self.get_canonical_query_string(_request.query)
        canonicalized_headers, signed_headers = self.handle_headers(
            _request.headers, canonicalized=True
        )

        _request.headers = self.handle_headers(_request.headers, canonicalized=False)

        canonical_request = (
            f"{_request.method}\n"
            f"{_request.pathname}\n"
            f"{canonicalized_query}\n"
            f"{canonicalized_headers}\n"
            f"{signed_headers}\n"
            f"{payload}"
        )

        str_to_sign = f'{sign_type}\n{self.hex_encode(self.hash_bytes(canonical_request.encode("utf-8"), sign_type))}'
        signature = self.hex_encode(
            self.signature_method(secret, str_to_sign, sign_type)
        )
        auth = f"{sign_type} Credential={ak},SignedHeaders={signed_headers},Signature={signature}"
        return auth


class AliDDNS:
    work_dir = os.path.dirname(__file__)
    ini_config = configparser.ConfigParser()  # 实例化ConfigParser
    record_file = os.path.join(work_dir, "aliyun_domain_record.ini")  # 解析记录配置
    utils = Utils()

    def __init__(self):
        """
        配置文件初始化
        """
        self.args = sys.argv
        if len(self.args) <= 1:
            self.config_file = os.path.join(self.work_dir, "config.ini")
        else:
            self.config_file = self.args[1]
        if not os.path.exists(self.config_file):
            self.utils.printer(ERROR, f"获取不到配置文件:", self.config_file)
            sys.exit()

        self.ini_config.read(self.config_file, encoding="utf-8")
        self.pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        try:
            self.pub_ip_url = self.ini_config.get("service", "pub_ip_url")
            self.end_point = self.ini_config.get("account", "end_point")
            self.access_key_id = self.ini_config.get("account", "access_key_id")
            self.access_key_secret = self.ini_config.get("account", "access_key_secret")
            self.domain_name = self.ini_config.get("domain", "domain_name")
            self.rr_key_word = self.ini_config.get("domain", "rr_key_word")
            self.type_key_word = self.ini_config.get("domain", "type_key_word")
            self.smtp_host = self.ini_config.get("mail", "smtp_host")
            self.smtp_port = int(self.ini_config.get("mail", "smtp_port"))
            self.smtp_ssl = self.ini_config.get("mail", "smtp_ssl")
            self.mail_sender = self.ini_config.get("mail", "sender")
            self.mail_user = self.ini_config.get("mail", "user")
            self.mail_passwd = self.ini_config.get("mail", "passwd")
            self._pre_match_mail = self.ini_config.get("mail", "send_to").split(",")
        except configparser.NoOptionError as NoOptionError:
            self.utils.printer(ERROR, "获取不到配置项:", NoOptionError)
            sys.exit()
        except configparser.NoSectionError as NoSectionError:
            self.utils.printer(ERROR, "获取不到配置节:", NoSectionError)
            sys.exit()
        except Exception as GetConfigError:
            self.utils.printer(ERROR, "错误的配置项:", GetConfigError)
            sys.exit()
        self.send_list = []
        if not re.match(self.pattern, self.mail_user):
            self.utils.printer(ERROR, "错误的邮箱地址:", self.mail_user)
            sys.exit()
        for mail in self._pre_match_mail:
            if not re.match(self.pattern, mail):
                self.utils.printer(ERROR, "错误的邮箱地址:", mail)
            else:
                self.send_list.append(mail)

    def _read_record_config(self) -> dict:
        """
        读取解析记录配置
        :return: dict
        """
        if not os.path.exists(self.record_file):
            self.utils.printer(INFO, "获取不到配置文件:", self.record_file)
            current_record = self._describe_record()
            with open(self.record_file, "w") as record_file:
                record_file.write(
                    "[domain_record]\nid={}\nvalue={}\ntime={}".format(
                        current_record["record_id"],
                        current_record["record_value"],
                        self.utils.get_unix_time(),
                    )
                )
        try:
            self.ini_config.read(self.record_file)
            record_id = self.ini_config.get("domain_record", "id")
            record_value = self.ini_config.get("domain_record", "value")
            write_time = self.ini_config.get("domain_record", "time")
            return {
                "record_id": record_id,
                "record_value": record_value,
                "write_time": write_time,
            }
        except configparser.NoSectionError as NoSectionError:
            self.utils.printer(INFO, "获取不到配置节:", NoSectionError)
            current_record = self._describe_record()
            with open(self.record_file, "w") as record_file:
                record_file.write(
                    "[domain_record]\nid={}\nvalue={}\ntime={}".format(
                        current_record["record_id"],
                        current_record["record_value"],
                        self.utils.get_unix_time(),
                    )
                )
            self.ini_config.read(self.record_file)
            record_id = self.ini_config.get("domain_record", "id")
            record_value = self.ini_config.get("domain_record", "value")
            write_time = self.ini_config.get("domain_record", "time")
            return {
                "record_id": record_id,
                "record_value": record_value,
                "write_time": write_time,
            }

    def _update_record_config(self, record_id: str, record_value: str) -> None:
        """
        更新解析记录配置
        :param record_id: 记录ID
        :param record_value: 记录值
        """
        update_config = configparser.ConfigParser()
        with open(self.record_file, "w") as configfile:
            update_config["domain_record"] = {}
            update_config["domain_record"]["id"] = record_id
            update_config["domain_record"]["value"] = record_value
            update_config["domain_record"]["time"] = str(self.utils.get_unix_time())
            update_config.write(configfile)

    def _get_pubic_ipaddr(self) -> str:
        """
        获取公网IPv4地址
        :return: str(ip_address)
        """
        try:
            with urllib.request.urlopen(self.pub_ip_url) as response:
                ip = response.read().decode("utf-8").strip()
        except Exception as GetPubicIpERROR:
            self.utils.printer(ERROR, "获取公网IP失败:", GetPubicIpERROR)
            sys.exit()
        return ip

    def _handle_request(self, action, data=None) -> Any:
        utils = self.utils
        headers = {
            "accept": "application/json",
            "host": self.end_point,
            "user-agent": utils.get_agent(),
            "x-acs-date": utils.get_timestamp(utc=True),
            "x-acs-signature-nonce": utils.get_nonce(),
            "x-acs-version": utils.acs_version,
        }
        hashed_request_payload = utils.hex_encode(
            utils.hash_bytes(b"", utils.signature_algorithm)
        )
        headers["x-acs-content-sha256"] = hashed_request_payload

        request = Request()
        request.headers = headers

        if action == UPDATE:
            record_id, value = data
            url = f"https://{self.end_point}/?RR={self.rr_key_word}&RecordId={record_id}&Type={self.type_key_word}&Value={value}"
            headers["x-acs-action"] = "UpdateDomainRecord"
            request.query = {
                "RR": self.rr_key_word,
                "RecordId": record_id,
                "Type": self.type_key_word,
                "Value": value,
            }
        elif action == DESCRIBE:
            url = f"https://{self.end_point}/?DomainName={self.domain_name}&RRKeyWord={self.rr_key_word}"
            request.headers["x-acs-action"] = "DescribeDomainRecords"
            request.query = {
                "DomainName": self.domain_name,
                "RRKeyWord": self.rr_key_word,
            }
        else:
            self.utils.printer(ERROR, "未知的action:", action)
            sys.exit()

        authorization = utils.get_authorization(
            request,
            utils.signature_algorithm,
            hashed_request_payload,
            self.access_key_id,
            self.access_key_secret,
        )
        request.headers["Authorization"] = authorization

        req = urllib.request.Request(
            url, data=None, headers=request.headers, method="POST"
        )
        with urllib.request.urlopen(
            req, context=ssl._create_unverified_context()
        ) as response:
            response = response.read().decode("utf-8")
            response = json.loads(response)

        if action == DESCRIBE:
            return response["DomainRecords"]

    def _describe_record(self) -> Any:
        """
        查询解析记录
        :return: dict & bool(false)
        """
        try:
            response = self._handle_request(DESCRIBE)
        except Exception as DescribeError:
            self.utils.printer(ERROR, "查询域名主机记录失败:", DescribeError)
            self._send_mail(
                self.send_list,
                "[{}][FAIL]DescribeDomainRecord".format(self.domain_name),
                "域名 {} 主机记录 {} 的值于 {} 查询失败, 原因:\n\n{}".format(
                    self.domain_name,
                    self.rr_key_word,
                    self.utils.get_timestamp(),
                    DescribeError,
                ),
            )
            return False
        record = response["Record"][0]
        record_value = record["Value"]
        record_id = record["RecordId"]
        return {"record_id": record_id, "record_value": record_value}

    def _update_record(self, record_id: str, record_value: str) -> bool:
        """
        更新解析记录
        :param record_id: 记录ID
        :param record_value: 记录值
        :return: bool
        """
        try:
            self._handle_request(UPDATE, data=[record_id, record_value])
            self._send_mail(
                self.send_list,
                "[{}][PASS]UpdateDomainRecord".format(self.domain_name),
                "域名 {} 主机记录 {} 的值于 {} 变更成功, 新的值为 {}".format(
                    self.domain_name,
                    self.rr_key_word,
                    self.utils.get_timestamp(),
                    record_value,
                ),
            )
            return True
        except Exception as UpdateError:
            self.utils.printer(ERROR, "更新域名主机记录失败:", UpdateError)
            self._send_mail(
                self.send_list,
                "[{}][FAIL]UpdateDomainRecord".format(self.domain_name),
                "域名 {} 主机记录 {} 的值于 {} 变更失败, 原因:\n\n{}".format(
                    self.domain_name,
                    self.rr_key_word,
                    self.utils.get_timestamp(),
                    UpdateError,
                ),
            )
            return False

    def _send_mail(self, to_address: list, header: str, msg: str) -> None:
        """
        发送邮件
        :param to_address: list(mail_list)
        :param header: str
        :param msg: str
        :return: none
        """
        smtp = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
        try:
            smtp.login(self.mail_user, self.mail_passwd)
        except Exception as SmtpLoginError:
            self.utils.printer(ERROR, "SMTP登陆失败:", SmtpLoginError)
            return
        message = MIMEText(msg, "plain", "utf-8")
        message["From"] = Header(self.mail_sender, "utf-8")
        message["Subject"] = Header(header, "utf-8")
        for addr in to_address:
            message["To"] = Header(addr, "utf-8")
            smtp.sendmail(self.mail_user, addr, message.as_string())
        smtp.quit()
        return

    def main(self) -> None:
        """
        主入口
        :return: none
        """
        current_config = self._read_record_config()
        current_ip = self._get_pubic_ipaddr()
        if current_ip != current_config["record_value"]:
            update_result = self._update_record(current_config["record_id"], current_ip)
            self._update_record_config(current_config["record_id"], current_ip)
            if update_result:
                current_config = self._read_record_config()
                self.utils.printer(INFO, "更新域名主机记录成功:", current_config)
        sys.exit()


if __name__ == "__main__":
    service = AliDDNS()
    service.main()
