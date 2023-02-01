# Aliyun-DDNS

部署在本地的阿里云DDNS更新脚本

## 简介

这是一个由Python编写的阿里云DDNS脚本，可以自动查询执行脚本机器的当前公网IP并与域名中某个A类主机记录比对。

如执行脚本机器当前公网IP与主机记录值有差异就会进行值更新，并使用`print()`函数进行打印，如值相同则不打印。

## 脚本原理

**查询DNS记录值**：AccessKey ID与AccessKey Secret创建连接请求 -> 使用主机记录查询RecordId -> 使用RecordId查询记录值

**查询公网IP**：使用[checkip.amazonaws.com](http://checkip.amazonaws.com)查询公网IP值

## 使用说明

部署前请修改`main.py`中5处值：

```
access_key_id='AccessKey ID',         # 填入你阿里云的AccessKey ID
access_key_secret='AccessKey Secret'  # 填入你阿里云的AccessKey Secret
rr='dns',                             # 要更改的主机记录
domain_name='qqays.xyz',              # 你的域名
rrkey_word='dns'                      # 要更改的主机记录
```

1. 使用`pip3 install`安装如下软件包。

```
alibabacloud_alidns20150109==3.0.1, requests~=2.28.2, jsonpath~=0.82, ntplib~=0.4.0
```

2. 使用`crontab -e`添加定时执行并追加输出结果至文件。
```
*/5 * * * * python3 /root/Aliyun-DDNS-main/main.py >> /root/Aliyun-DDNS-main/DDNS.log
```

## 效果

![DDNS.log](https://i.328888.xyz/2023/02/01/8LNyv.png)

## 相关链接

[阿里云-RAM访问控制-创建AccessKey](https://ram.console.aliyun.com/manage/ak)

[阿里云-云解析-API](https://next.api.aliyun.com/api/Alidns/2015-01-09)
