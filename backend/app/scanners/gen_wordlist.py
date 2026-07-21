import os

OUT = os.path.join(os.path.dirname(__file__), "data", "subdomains_2000.txt")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

# Curated common subdomain labels (business / infra / app / regional).
base = [
    "www","mail","email","smtp","pop","pop3","imap","ns1","ns2","ns3","ns4","dns1","dns2",
    "web","web1","web2","webmail","remote","ssh","ftp","ftps","sftp","ssl","vpn","vpno",
    "admin","administrator","root","dev","devel","stage","staging","test","testing","qa",
    "uat","prod","production","demo","beta","alpha","preview","sandbox","lab","old","new",
    "api","api1","api2","apis","mobile","m","app","apps","portal","cp","cpanel","whm",
    "plesk","directadmin","webmin","panel","dashboard","manage","console","login","auth",
    "sso","oauth","secure","safebrowsing","gateway","gw","proxy","vpn1","vpn2","router",
    "firewall","fw","lb","loadbalancer","balancer","cdn","cdn1","cdn2","static","assets",
    "media","img","images","image","video","videos","stream","streaming","live","chat",
    "support","help","helpdesk","docs","doc","documentation","wiki","kb","blog","news",
    "forum","community","shop","store","cart","checkout","pay","payment","payments","billing",
    "invoice","accounts","account","billing2","order","orders","client","clients","customer",
    "partner","partners","vendor","vendors","affiliate","affiliates","reseller","distributor",
    "status","statuspage","monitor","monitoring","metrics","grafana","kibana","prometheus",
    "alert","alerts","logging","log","logs","elk","graylog","sentry","uptime","pingdom",
    "db","database","mysql","mssql","pgsql","postgres","postgresql","mongo","mongodb","redis",
    "cache","memcached","elastic","elasticsearch","solr","neo4j","cassandra","influx","influxdb",
    "rabbitmq","kafka","queue","jenkins","ci","cd","build","builder","pipeline","git","gitlab",
    "github","svn","hg","nexus","artifactory","registry","docker","k8s","kubernetes","rancher",
    "openshift","nomad","consul","vault","terraform","ansible","puppet","chef","salt","zabbix",
    "nagios","cacti","munin","ntop","speedtest","test1","test2","test3","dev1","dev2","dev3",
    "stage1","stage2","old1","old2","backup","backups","bk","bak","archive","archives","tmp",
    "temp","junk","internal","intranet","intra","private","lan","local","corp","company","office",
    "hr","finance","fin","sales","marketing","mkt","it","ops","sec","security","soc","grc",
    "legal","compliance","go","go2","mta","mx","relay","mail1","mail2","smtp1","smtp2","imap1",
    "autodiscover","autoconfig","exchange","owa","ecp","activesync","lync","sip","voip","pbx",
    "freepbx","asterisk","teams","webex","zoom","jitsi","mattermost","slack","rocket","discourse",
    "list","lists","ml","newsletter","campaign","marketo","hubspot","salesforce","sfdc","zendesk",
    "freshdesk","jira","confluence","bitbucket","trello","asana","notion","airtable","smartsheet",
    "tableau","powerbi","looker","metabase","redash","superset","erp","sap","oracle","dynamics",
    "netsuite","quickbooks","xero","magento","shopify","woo","wordpress","wp","drupal","joomla",
    "laravel","symfony","django","rails","node","nodejs","express","spring","tomcat","jboss",
    "weblogic","websphere","glassfish","jetty","nginx","apache","iis","litespeed","caddy","haproxy",
    "traefik","envoy","varnish","squid","auth0","okta","onelogin","pingfederate","keycloak",
    "cas","adfs","radius","ldap","ldaps","ad","ads","domain","print","printer","spiceworks",
    "manageengine","solarwinds","kaseya","connectwise","bitwarden","vaultui","passbolt","keepass",
    "download","downloads","updates","update","files","file","fileserver","share","shares","nfs",
    "smb","ftp1","ftp2","sftp1","webdav","dav","cal","calendar","carddav","contacts","gateway1",
    "edge","edge1","origin","origin1","front","frontend","backend","be","fe","service","services",
    "svc","micro","micro1","gateway2","eu","us","uk","de","fr","asia","eu1","us1","apac","latam",
]

# Expand with numbered variants to reach ~2000.
words = list(dict.fromkeys([w.strip() for w in base if w.strip()]))
# Add numbered suffixes 01-20 for the most useful prefixes.
numbered_prefixes = ["dev","stage","staging","test","prod","api","db","cache","web","mail",
                     "app","admin","vpn","ns","dns","smtp","ftp","sftp","redis","pg","mysql",
                     "node","svc","worker","job","batch","worker1","admin1","auth","login",
                     "cdn","static","media","img","beta","demo","old","new","qa","uat"]
for p in numbered_prefixes:
    for i in range(1, 51):
        words.append(f"{p}{i:02d}")

# Add regional + env combos
for env in ["dev","stage","prod","test","uat","qa","demo","beta","old","new","api","web","db","cache","admin","vpn"]:
    for reg in ["eu","us","uk","de","asia","apac","latam","na","emea","sa","ca","au","in","sg","jp","fr"]:
        words.append(f"{env}-{reg}")
        words.append(f"{reg}-{env}")

# De-dup preserving order, cap at 2000.
seen = set()
out = []
for w in words:
    if w not in seen:
        seen.add(w)
        out.append(w)
    if len(out) >= 2000:
        break

with open(OUT, "w") as f:
    f.write("\n".join(out) + "\n")

print("wrote", len(out), "words to", OUT)
