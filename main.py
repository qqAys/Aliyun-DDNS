# -*- coding: utf-8 -*-

#  Copyright (c) 2023. Lorem ipsum dolor sit amet, consectetur adipiscing elit.
#  Morbi non lorem porttitor neque feugiat blandit. Ut vitae ipsum eget quam lacinia accumsan.
#  Etiam sed turpis ac ipsum condimentum fringilla. Maecenas magna.
#  Proin dapibus sapien vel ante. Aliquam erat volutpat. Pellentesque sagittis ligula eget metus.
#  Vestibulum commodo. Ut rhoncus gravida arcu.

# @Time          : 2023/1/14 10:26
# @Author        : Jinx
# @Email-Private : me@qqays.xyz
# @Github        : https://github.com/qqAys
# @Description   : 使用python编写的阿里云DDNS脚本，部署前请pip安装软件包: requirements.txt

import datetime
import json

import ntplib
import requests
from alibabacloud_alidns20150109 import models as alidns_20150109_models
from alibabacloud_alidns20150109.client import Client as Alidns20150109Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient
from jsonpath import jsonpath


class DDNS:
    def __init__(self):
        pass

    @staticmethod
    def create_client():
        config = open_api_models.Config(
            access_key_id='AccessKey ID',  # 填入你阿里云的AccessKey ID
            access_key_secret='AccessKey Secret'  # 填入你阿里云的AccessKey Secret
        )
        config.endpoint = 'alidns.cn-shenzhen.aliyuncs.com'  # 可不必更改
        return Alidns20150109Client(config)

    @staticmethod
    def update(record_id: str, ip: str):
        client = DDNS.create_client()
        update_domain_record_request = alidns_20150109_models.UpdateDomainRecordRequest(
            record_id=record_id,
            rr='dns',  # 要更改的主机记录
            type='A',
            value=ip
        )
        runtime = util_models.RuntimeOptions()
        client.update_domain_record_with_options(update_domain_record_request, runtime)

    @staticmethod
    def describe():
        client = DDNS.create_client()
        describe_domain_records_request = alidns_20150109_models.DescribeDomainRecordsRequest(
            domain_name='qqays.xyz',  # 你的域名
            rrkey_word='dns'  # 要更改的主机记录
        )
        runtime = util_models.RuntimeOptions()
        resp = client.describe_domain_records_with_options(describe_domain_records_request, runtime)
        request = json.loads(UtilClient.to_jsonstring(resp))
        record_value = jsonpath(request, '$...Value')
        record_id = jsonpath(request, '$...RecordId')
        return record_value[0], record_id[0]

    @staticmethod
    def get_ntp_time():
        ntp_client = ntplib.NTPClient()
        response = ntp_client.request('cn.ntp.org.cn')
        return datetime.datetime.fromtimestamp(response.tx_time)


if __name__ == '__main__':
    date_time = DDNS.get_ntp_time()
    dns_ip = DDNS.describe()[0]
    record_id = DDNS.describe()[1]
    pub_ip = requests.get('http://checkip.amazonaws.com').text.strip()
    if dns_ip != pub_ip:
        old_record = DDNS.describe()[0]
        try:
            DDNS.update(record_id, pub_ip)
            new_record = DDNS.describe()[0]
            print(f'{date_time}  Success: DNS record {old_record} --> {new_record}')
        except Exception as update_error:
            print(f'{date_time}  {update_error}')
