# -*- coding: utf-8 -*-

#  Copyright (c) 2023. Lorem ipsum dolor sit amet, consectetur adipiscing elit.
#  Morbi non lorem porttitor neque feugiat blandit. Ut vitae ipsum eget quam lacinia accumsan.
#  Etiam sed turpis ac ipsum condimentum fringilla. Maecenas magna.
#  Proin dapibus sapien vel ante. Aliquam erat volutpat. Pellentesque sagittis ligula eget metus.
#  Vestibulum commodo. Ut rhoncus gravida arcu.

# @Time          : 2023/12/05 10:26
# @Author        : Jinx
# @Email-Private : me@qqays.xyz
# @Github        : https://github.com/qqAys
# @Description   : 使用python编写的阿里云DDNS脚本,基于V2.0的SDK,部署前请pip安装软件包: requirements.txt


import configparser
import json
import os
import re
import smtplib
import sys
import time
from email.header import Header
from email.mime.text import MIMEText

import requests
from alibabacloud_alidns20150109 import models as alidns_20150109_models
from alibabacloud_alidns20150109.client import Client as Alidns20150109Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient
from jsonpath import jsonpath


def get_readable_time():
    """
    基于当前时间戳, 获取可读性强的时间
    :return: eg. 2023-12-05 14:18:06
    """
    timestamp = int(time.time())
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))


def get_timestamp():
    """
    获取当前时间戳
    :return: 时间戳
    """
    return int(time.time())


class AliDDNS:
    work_dir = os.path.dirname(__file__)
    ini_config = configparser.ConfigParser()  # 实例化ConfigParser
    record_file = os.path.join(work_dir, 'aliyun_domain_record.ini')  # 解析记录配置

    def __init__(self):
        """
        配置文件初始化
        """
        self.args = sys.argv
        if len(self.args) <= 1:
            self.config_file = os.path.join(self.work_dir, 'config.ini')
        else:
            self.config_file = self.args[1]
        if not os.path.exists(self.config_file):
            print('{} [ERROR] 获取不到配置文件: {}'.format(get_readable_time(), self.config_file))
            sys.exit()

        self.ini_config.read(self.config_file)
        self.pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        try:
            self.pub_ip_url = self.ini_config.get('service', 'pub_ip_url')
            self.end_point = self.ini_config.get('account', 'end_point')
            self.access_key_id = self.ini_config.get('account', 'access_key_id')
            self.access_key_secret = self.ini_config.get('account', 'access_key_secret')
            self.domain_name = self.ini_config.get('domain', 'domain_name')
            self.rr_key_word = self.ini_config.get('domain', 'rr_key_word')
            self.type_key_word = self.ini_config.get('domain', 'type_key_word')
            self.smtp_host = self.ini_config.get('mail', 'smtp_host')
            self.smtp_port = int(self.ini_config.get('mail', 'smtp_port'))
            self.smtp_ssl = self.ini_config.get('mail', 'smtp_ssl')
            self.mail_sender = self.ini_config.get('mail', 'sender')
            self.mail_user = self.ini_config.get('mail', 'user')
            self.mail_passwd = self.ini_config.get('mail', 'passwd')
            self._pre_match_mail = self.ini_config.get('mail', 'send_to').split(',')
        except configparser.NoOptionError as NoOptionError:
            print('{} [ERROR] 获取不到配置项: {}'.format(get_readable_time(), NoOptionError))
            sys.exit()
        except configparser.NoSectionError as NoSectionError:
            print('{} [ERROR] 获取不到配置节: {}'.format(get_readable_time(), NoSectionError))
            sys.exit()
        except Exception as GetConfigError:
            print('{} [ERROR] 错误的配置项: {}'.format(get_readable_time(), GetConfigError))
            sys.exit()
        self.send_list = []
        if not re.match(self.pattern, self.mail_user):
            print('{} [ERROR] 错误的邮箱地址: {}'.format(get_readable_time(), self.mail_user))
            sys.exit()
        for mail in self._pre_match_mail:
            if not re.match(self.pattern, mail):
                print('{} [WARNING] 错误的邮箱地址: {}'.format(get_readable_time(), mail))
            else:
                self.send_list.append(mail)

    def _read_record_config(self):
        """
        读取解析记录配置
        :return: dict
        """
        if not os.path.exists(self.record_file):
            print('{} [INFO] 获取不到配置文件: {}'.format(get_readable_time(), self.record_file))
            with open('{}'.format(self.record_file), 'w') as record_file:
                record_file.write(
                    '[domain_record]\nid={}\nvalue={}\ntime={}'
                    .format(
                        self.describe_record()['record_id'],
                        self.describe_record()['record_value'],
                        get_timestamp()
                    )
                )
        try:
            self.ini_config.read(self.record_file)
            record_id = self.ini_config.get('domain_record', 'id')
            record_value = self.ini_config.get('domain_record', 'value')
            write_time = self.ini_config.get('domain_record', 'time')
            return {'record_id': record_id, 'record_value': record_value, 'write_time': write_time}
        except configparser.NoSectionError as NoSectionError:
            print('{} [INFO] 获取不到配置节: {}'.format(get_readable_time(), NoSectionError))
            with open('{}'.format(self.record_file), 'w') as record_file:
                record_file.write(
                    '[domain_record]\nid={}\nvalue={}\ntime={}'
                    .format(
                        self.describe_record()['record_id'],
                        self.describe_record()['record_value'],
                        get_timestamp()
                    )
                )
            self.ini_config.read(self.record_file)
            record_id = self.ini_config.get('domain_record', 'id')
            record_value = self.ini_config.get('domain_record', 'value')
            write_time = self.ini_config.get('domain_record', 'time')
            return {'record_id': record_id, 'record_value': record_value, 'write_time': write_time}

    def _update_record_config(self, record_id: str, record_value: str):
        """
        更新解析记录配置
        :param record_id: 记录ID
        :param record_value: 记录值
        """
        update_config = configparser.ConfigParser()
        with open(self.record_file, 'w') as configfile:
            update_config['domain_record'] = {}
            update_config['domain_record']['id'] = record_id
            update_config['domain_record']['value'] = record_value
            update_config['domain_record']['time'] = str(get_timestamp())
            update_config.write(configfile)

    def _get_pubic_ipaddr(self):
        """
        获取公网IPv4地址
        :return: str(ip_address)
        """
        try:
            ip = requests.get(self.pub_ip_url).text.strip()
        except Exception as GetPubicIpERROR:
            print('{} [ERROR] 获取公网IP失败: {}'.format(get_readable_time(), GetPubicIpERROR))
            sys.exit()
        return ip

    def _create_client(self):
        """
        创建阿里DNS客户端
        :return: client
        """
        config = open_api_models.Config(
            access_key_id=self.access_key_id,
            access_key_secret=self.access_key_secret,
            endpoint=self.end_point
        )
        return Alidns20150109Client(config)

    def describe_record(self):
        """
        查询解析记录
        :return: dict & bool(false)
        """
        client = self._create_client()
        describe_domain_records_request = alidns_20150109_models.DescribeDomainRecordsRequest(
            domain_name=self.domain_name,
            rrkey_word=self.rr_key_word
        )
        runtime = util_models.RuntimeOptions()
        try:
            resp = client.describe_domain_records_with_options(describe_domain_records_request, runtime)
        except Exception as DescribeError:
            print('{} [ERROR] 查询域名主机记录失败: {}'.format(get_readable_time(), DescribeError))
            self.send_mail(
                self.send_list,
                '[{}][FAIL]DescribeDomainRecord'.format(self.domain_name),
                '域名 {} 主机记录 {} 的值于 {} 查询失败, 原因:\n\n{}'
                .format(
                    self.domain_name,
                    self.rr_key_word,
                    get_readable_time(),
                    DescribeError
                )
            )
            return False
        request = json.loads(UtilClient.to_jsonstring(resp))
        record_value = jsonpath(request, '$...Value')[0]
        record_id = jsonpath(request, '$...RecordId')[0]
        return {'record_id': record_id, 'record_value': record_value}

    def update_record(self, record_id: str, record_value: str):
        """
        更新解析记录
        :param record_id: 记录ID
        :param record_value: 记录值
        :return: bool
        """
        client = self._create_client()
        update_domain_record_request = alidns_20150109_models.UpdateDomainRecordRequest(
            record_id=record_id,
            rr=self.rr_key_word,
            type=self.type_key_word,
            value=record_value
        )
        runtime = util_models.RuntimeOptions()
        try:
            client.update_domain_record_with_options(update_domain_record_request, runtime)
            self.send_mail(
                self.send_list,
                '[{}][PASS]UpdateDomainRecord'.format(self.domain_name),
                '域名 {} 主机记录 {} 的值于 {} 变更成功, 新的值为 {}'
                .format(
                    self.domain_name,
                    self.rr_key_word,
                    get_readable_time(),
                    record_value
                )
            )
            return True
        except Exception as UpdateError:
            print('{} [ERROR] 更新域名主机记录失败: {}'.format(get_readable_time(), UpdateError))
            self.send_mail(
                self.send_list,
                '[{}][FAIL]UpdateDomainRecord'.format(self.domain_name),
                '域名 {} 主机记录 {} 的值于 {} 变更失败, 原因:\n\n{}'
                .format(
                    self.domain_name,
                    self.rr_key_word,
                    get_readable_time(),
                    UpdateError
                )
            )
            return False

    def send_mail(self, to_addrs: list, header: str, msg: str):
        """
        发送邮件
        :param to_addrs: list(mail_list)
        :param header: str
        :param msg: str
        :return: none
        """
        smtp = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)
        try:
            smtp.login(self.mail_user, self.mail_passwd)
        except Exception as SmtpLoginError:
            print('{} [ERROR] SMTP登陆失败: {}'.format(get_readable_time(), SmtpLoginError))
            return
        message = MIMEText(msg, 'plain', 'utf-8')
        message['From'] = Header(self.mail_sender, 'utf-8')
        message['Subject'] = Header(header, 'utf-8')
        for addr in to_addrs:
            message['To'] = Header(addr, 'utf-8')
            smtp.sendmail(self.mail_user, addr, message.as_string())
        smtp.quit()
        return

    def main(self):
        """
        主入口
        :return: none
        """
        current_config = self._read_record_config()
        current_ip = self._get_pubic_ipaddr()
        if current_ip != current_config['record_value']:
            update_result = self.update_record(current_config['record_id'], current_ip)
            self._update_record_config(current_config['record_id'], current_ip)
            if update_result:
                current_config = self._read_record_config()
                print('{} [SUCCESS] 更新域名主机记录成功: {}'.format(get_readable_time(), current_config))
        sys.exit()


if __name__ == '__main__':
    service = AliDDNS()
    service.main()
