import argparse
import json
import logging
import random
import smtplib
from email.header import Header
from email.mime.text import MIMEText
from pathlib import Path

import requests
import yaml
from alibabacloud_alidns20150109 import models as alidns_20150109_models
from alibabacloud_alidns20150109.client import Client as Alidns20150109Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient
from jsonpath import jsonpath

logger = logging.getLogger(__name__)

console_handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s | %(levelname)s >>> %(message)s")
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)


class AliyunDDNS:

    def __init__(self):
        parser = argparse.ArgumentParser(
            description="Aliyun-DDNS by Jinx@qqAys in Dec. 2024"
        )
        parser.add_argument(
            "--config_file", "-c", type=str, required=False, help="自定义配置路径"
        )
        parser.add_argument(
            "--debug", required=False, action="store_true", help="打开调试"
        )
        args = parser.parse_args()

        if args.debug is True:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        self.config_file = None
        self.parse_args(args)

        config: dict = self.parse_config()

        self.temp_data_file = Path(Path.home(), ".ddns_data")
        self.temp_data_file.touch(exist_ok=True)

        self.public_ip_config: dict = config.get("public_ip")

        self.access_key_id: str = config.get("account").get("access_key_id")
        self.access_key_secret: str = config.get("account").get("access_key_secret")

        self.dns_end_point: str = config.get("domain").get("dns_end_point")
        self.domain_name: str = config.get("domain").get("name")
        self.rr_key_word: str = config.get("domain").get("rr")
        self.type_key_word: str = config.get("domain").get("type")

        self.remote_record_id = None

        self.smtp_config: dict = config.get("smtp")

    def parse_args(self, args):
        self.config_file = Path("./config.yml")
        if args.config_file is not None:
            custom_config_file = Path(args.config_file)
            if custom_config_file.exists():
                self.config_file = custom_config_file
            else:
                logger.error(f"{custom_config_file} 配置文件不存在")

    def parse_config(self):
        with open(self.config_file, "r", encoding="utf-8") as config_file:
            return yaml.safe_load(config_file)

    def parse_temp_data(self):
        with open(self.temp_data_file, "r", encoding="utf-8") as temp_data_file:
            return yaml.safe_load(temp_data_file)

    def save_temp_data(self, current_ip):
        data = {"current_ip": current_ip, "remote_record_id": self.remote_record_id}
        with open(self.temp_data_file, "w", encoding="utf-8") as temp_data_file:
            return temp_data_file.write(yaml.dump(data))

    def fetch_current_ip(self):
        logger.info("获取当前公网IP地址...")

        urls = self.public_ip_config.get("urls", ["https://checkip.amazonaws.com/"])
        requests_timeout = self.public_ip_config.get("timeout", 5) / 2

        # 抽样
        if len(urls) >= 2:
            urls = random.sample(urls, k=2)

        url_a, url_b = urls

        try:
            logger.debug(f"开始请求 [{url_a}]")
            ip_a = (
                requests.get(url_a, timeout=(requests_timeout, requests_timeout))
                .content.decode("utf-8")
                .replace("\n", "")
            )
            logger.debug(f"ip_a[{url_a}] {ip_a}")

            logger.debug(f"开始请求 [{url_b}]")
            ip_b = (
                requests.get(url_b, timeout=(requests_timeout, requests_timeout))
                .content.decode("utf-8")
                .replace("\n", "")
            )
            logger.debug(f"ip_b[{url_b}] {ip_b}")
        except Exception as e:
            logger.error(f"请求错误, {e}")
            return None

        if ip_a == ip_b:
            logger.info(f"获取公网IP地址完成 {ip_a}")
            return ip_a
        else:
            logger.error(f"公网IP存在异常，[{urls[0]}]{ip_a} != [{urls[1]}]{ip_b}")
            return None

    def create_client(self):
        config = open_api_models.Config(
            access_key_id=self.access_key_id,
            access_key_secret=self.access_key_secret,
            endpoint=self.dns_end_point,
        )
        return Alidns20150109Client(config)

    def describe_record(self):
        client = self.create_client()
        describe_domain_records_request = (
            alidns_20150109_models.DescribeDomainRecordsRequest(
                domain_name=self.domain_name, rrkey_word=self.rr_key_word
            )
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = client.describe_domain_records_with_options(
                describe_domain_records_request, runtime
            )
            response_json = json.loads(UtilClient.to_jsonstring(response))
            record_value = jsonpath(response_json, "$...Value")[0]
            self.remote_record_id = jsonpath(response_json, "$...RecordId")[0]
            return record_value
        except Exception as DescribeError:
            logger.error(DescribeError)
            return None

    def update_record(self, record_value: str):
        client = self.create_client()
        update_domain_record_request = alidns_20150109_models.UpdateDomainRecordRequest(
            record_id=self.remote_record_id,
            rr=self.rr_key_word,
            type=self.type_key_word,
            value=record_value,
        )
        runtime = util_models.RuntimeOptions()
        try:
            client.update_domain_record_with_options(
                update_domain_record_request, runtime
            )
            return True
        except Exception as UpdateError:
            logger.error(UpdateError)
            return False

    def send_mail(self, header: str, msg: str):
        if self.smtp_config.get("ssl") is True:
            smtp = smtplib.SMTP_SSL(
                self.smtp_config.get("host"), self.smtp_config.get("port")
            )
        else:
            smtp = smtplib.SMTP(
                self.smtp_config.get("host"), self.smtp_config.get("port")
            )
        try:
            smtp.login(
                self.smtp_config.get("username"), self.smtp_config.get("password")
            )
        except Exception as SmtpLoginError:
            logger.error(SmtpLoginError)
            return
        message = MIMEText(msg, "plain", "utf-8")
        message["From"] = Header(self.smtp_config.get("from_address"), "utf-8")
        message["Subject"] = Header(header, "utf-8")
        for address in self.smtp_config.get("to_addresses"):
            message["To"] = Header(address, "utf-8")
            smtp.sendmail(
                self.smtp_config.get("username"), address, message.as_string()
            )
        smtp.quit()
        return

    def run(self):
        logger.debug(f"正在读取 {self.temp_data_file}")
        temp_data = self.parse_temp_data()

        current_ip = self.fetch_current_ip()

        if current_ip is None:
            logger.error("当前IP获取失败，跳过此次运行")
            return

        if temp_data is None:
            logger.debug("内容为空")
            remote_ip = self.describe_record()

            if remote_ip != current_ip:
                logger.info("当前IP与远程记录IP不一致，将更改")
                update_result = self.update_record(current_ip)
                if update_result is False:
                    self.send_mail(
                        "[FAIL]UpdateDomainRecord",
                        f"{self.rr_key_word}.{self.domain_name} {remote_ip} --X {current_ip}",
                    )
                    logger.error("更改失败")
                else:
                    self.send_mail(
                        "[PASS]UpdateDomainRecord",
                        f"{self.rr_key_word}.{self.domain_name} {remote_ip} --> {current_ip}",
                    )
                    logger.info("更改成功")
            else:
                logger.info("当前IP与远程记录IP一致")
            self.save_temp_data(current_ip)
        else:
            logger.debug(f"读取完成 {temp_data}")
            temp_data_record_ip = temp_data["current_ip"]
            self.remote_record_id = temp_data["remote_record_id"]

            if current_ip != temp_data_record_ip:
                logger.info("当前IP与远程记录IP不一致，将更改")
                update_result = self.update_record(current_ip)
                if update_result is False:
                    self.send_mail(
                        "[FAIL]UpdateDomainRecord",
                        f"{self.rr_key_word}.{self.domain_name} {temp_data_record_ip} --X {current_ip}",
                    )
                    logger.error("更改失败")
                else:
                    self.send_mail(
                        "[PASS]UpdateDomainRecord",
                        f"{self.rr_key_word}.{self.domain_name} {temp_data_record_ip} --> {current_ip}",
                    )
                    self.save_temp_data(current_ip)
                    logger.info("更改成功")
            else:
                logger.info("当前IP与远程记录IP一致")


if __name__ == "__main__":
    service = AliyunDDNS()
    service.run()
