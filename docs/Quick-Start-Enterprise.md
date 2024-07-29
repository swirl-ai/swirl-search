---
layout: default
title: Quick Start - Enterprise
nav_order: 3
---
<details markdown="block">
  <summary>
    Table of Contents
  </summary>
  {: .text-delta }
- TOC
{:toc}
</details>

# Quick Start Guide

{: .warning }
This version applies to the Enterprise Edition of SWIRL! A valid license key is required.

* To run SWIRL in Docker, you must have the latest [Docker app](https://docs.docker.com/get-docker/) for MacOS, Linux, or Windows installed and running locally.

* You must be logged in to a valid Docker Hub by opening the command-line interface (CLI) and executing the following command, replacing <docker-username> and <docker-password> with your Docker Hub credentials.

``` shell
docker login --username <docker-username> --password <docker-password>
```

* Windows users must first install and configure either the WSL 2 or the Hyper-V backend, as outlined in the  [System Requirements for installing Docker Desktop on Windows](https://docs.docker.com/desktop/install/windows-install/#system-requirements).

{: .warning }
Make sure the Docker app is running before proceeding!

* On MacOS or Linux, run the following command from the Console:

``` shell
docker-compose pull && docker-compose up
```

* On Windows, run the following command from PowerShell:

``` shell
docker compose up
```

After a few minutes, the following or similar should appear:

``` shell
redis-1  | 1:C 05 Feb 2024 22:03:51.503 * oO0OoO0OoO0Oo Redis is starting oO0OoO0OoO0Oo
redis-1  | 1:C 05 Feb 2024 22:03:51.503 * Redis version=7.2.4, bits=64, commit=00000000, modified=0, pid=1, just started
redis-1  | 1:C 05 Feb 2024 22:03:51.503 # Warning: no config file specified, using the default config. In order to specify a config file use redis-server /path/to/redis.conf
redis-1  | 1:M 05 Feb 2024 22:03:51.504 * monotonic clock: POSIX clock_gettime
redis-1  | 1:M 05 Feb 2024 22:03:51.504 * Running mode=standalone, port=6379.
redis-1  | 1:M 05 Feb 2024 22:03:51.505 * Server initialized
redis-1  | 1:M 05 Feb 2024 22:03:51.505 * Ready to accept connections tcp
app-1    | __S_W_I_R_L__3_._2_._0__________________________________________________________
app-1    | 
app-1    | Setting Up Swirl:
app-1    | Checking Migrations:
app-1    | 
app-1    | Migrating:
app-1    | 
app-1    | Operations to perform:
app-1    |   Apply all migrations: admin, auth, authtoken, contenttypes, django_celery_beat, sessions, swirl
app-1    | Running migrations:
app-1    |   No migrations to apply.
app-1    | 
app-1    | 
app-1    | Collecting Statics:
app-1    | 
app-1    | 
app-1    | 246 static files copied to '/app/static'.
app-1    | 
app-1    | Ok
app-1    | Command successful!
app-1    | __S_W_I_R_L__3_._2_._0__________________________________________________________
app-1    | 
app-1    | Warning: logs directory does not exist, creating it
app-1    | ParseResult(scheme='redis', netloc='redis:6379', path='/0', params='', query='', fragment='') checked.
app-1    | ParseResult(scheme='redis', netloc='redis:6379', path='/0', params='', query='', fragment='') checked.
app-1    | Start: celery-worker -> celery -A swirl_server worker --loglevel INFO ... Ok, pid: 50
app-1    | Start: celery-beats -> celery -A swirl_server beat --scheduler django_celery_beat.schedulers:DatabaseScheduler ... Ok, pid: 72
app-1    | Updating .swirl... Ok
app-1    | 
app-1    |   PID TTY          TIME CMD
app-1    |    50 ?        00:00:03 celery
app-1    | 
app-1    | You're using version 3.2.0 of Swirl, the current version.
app-1    | Command successful!
app-1    | 2024-02-05 17:04:14,131 INFO     Starting server at tcp:port=8000:interface=0.0.0.0
app-1    | 2024-02-05 17:04:14,131 INFO     HTTP/2 support not enabled (install the http2 and tls Twisted extras)
app-1    | 2024-02-05 17:04:14,131 INFO     Configuring endpoint tcp:port=8000:interface=0.0.0.0
app-1    | 2024-02-05 17:04:14,132 INFO     Listening on TCP address 0.0.0.0:8000
```

* Open this URL with a browser: <http://localhost:8000> (or <http://localhost:8000/galaxy>)

If the search page appears, click `Log Out` at the top, right. The SWIRL login page will appear:

![SWIRL Login](images/swirl_login-galaxy_dark.png)

* Enter the username `admin` and password `password`, then click `Login`.

* Enter a search in the search box and press the `Search` button. Ranked results appear in just a few seconds:

![SWIRL Results No M365](images/swirl_results_no_m365-galaxy_dark.png)


* Click the `Generate AI Insight` button to RAG using the most relevant results, if you have specified an OpenAI key as noted earlier.

![SWIRL Results with RAG](images/swirl_rag_pulmonary_1.png)

* Click the profile avatar in the upper right corner of the Galaxy UI. Then click [Manage SWIRL](http://localhost:8000/swirl/) to explore the rest of SWIRL's features.

* To view the raw result JSON, click `Search` under the API section of the `Manage SWIRL` page linked above, or open <http://localhost:8000/swirl/search/>

The most recent Search object will be displayed at the top. Click on the `result_url` link to view the full JSON Response. For example:

![SWIRL JSON response](images/swirl_results_mixed_1.png)

* Read the [SWIRL User Guide](./User-Guide.md) for additional information.

## Notes

{: .warning }
The Docker version of SWIRL does *not* retain any data or configuration when shut down!

{: .highlight }
SWIRL includes five (5) Google Programmable Search Engines (PSEs) to get you up and running right away. The credentials for these are shared with the SWIRL Community.

{: .highlight }
Using SWIRL with Microsoft 365 requires installation and approval by an authorized company Administrator. For more information, please review the [M365 Guide](M365-Guide.md) or [contact us](mailto:hello@swirl.today).