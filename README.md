# Aliyun-DDNS

部署在本地的阿里云DDNS更新脚本

## 简介

这是一个由Python编写的阿里云DDNS脚本, 可以自动查询执行脚本机器的当前公网IP并与域名中某个A类主机记录比对。

如执行脚本机器当前公网IP与主机记录值有差异就会进行值更新, 并发送通知邮件。(异常情况也会进行通知)

## 脚本原理

查询DNS记录值: AccessKey ID与AccessKey Secret创建连接请求 -> 使用主机记录查询RecordId -> 使用RecordId查询记录值

查询公网IP: 使用[checkip.amazonaws.com](http://checkip.amazonaws.com)查询公网IP值(速度较慢), 可使用[service.qqays.xyz/my-ip](https://service.qqays.xyz/my-ip)进行公网IP值的查询。

## 使用

`main.py` 为集成阿里SDK版本, 需安装Python要求。`slim.py` 为模拟了阿里SDK请求, 无外部Python库依赖。

1. 克隆项目, 进入项目。

```shell
git clone https://github.com/qqAys/Aliyun-DDNS.git
cd Aliyun-DDNS
```

2. 安装Python要求。(slim无需执行该步骤)

```shell
pip3 install -r requirements.txt
```

3. 将配置文件重命名, 修改配置。(参见`config.ini.example`)

```shell
mv config.ini.example config.ini
```

4. 使用`crontab -e`添加定时执行。

```shell
# 使用 main.py
*/5 * * * * python3 /root/Aliyun-DDNS/main.py >> /root/Aliyun-DDNS/DDNS.log
# 或者指定配置文件路径参数
*/5 * * * * python3 /root/Aliyun-DDNS/main.py /opt/config.ini >> /root/Aliyun-DDNS/DDNS.log

# 使用 slim.py
*/5 * * * * python3 /root/Aliyun-DDNS/slim.py >> /root/Aliyun-DDNS/DDNS.log
# 或者指定配置文件路径参数
*/5 * * * * python3 /root/Aliyun-DDNS/slim.py /opt/config.ini >> /root/Aliyun-DDNS/DDNS.log
```

## 效果

![DDNS.log](https://qqays-mkdocs-blog.oss-cn-shenzhen.aliyuncs.com/uploads/2023/12/06/Snipaste_2023-12-06_09-49-35.png)

## 相关链接

[阿里云-RAM访问控制-创建AccessKey](https://ram.console.aliyun.com/manage/ak)

[阿里云-云解析-API](https://next.api.aliyun.com/api/Alidns/2015-01-09)
