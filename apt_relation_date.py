# coding=utf-8
import sys
from datetime import datetime, timedelta
from time import sleep
from collections import defaultdict
from pysolr import Solr
import pymysql

# from solr import SolrConnection
aps = ['Intelligence\ Gathering', 'Point\ of\ Entry', 'Command\ and\ Control\ Communication',
       'Lateral\ Movement', 'Asset\ and\ Data\ Discovery', 'Data\ Exfiltration']


def cal_attacks(ip_addr, today):
    tda_solr = Solr('{0}/solr/tda_{1}'.format(ip_addr, today))
    waf_solr = Solr('{0}/solr/waf_{1}'.format(ip_addr, today))
    ids_solr = Solr('{0}/solr/ids_{1}'.format(ip_addr, today))

    try:
        threat_types_result = tda_solr.search('*:*', facet='on', **{'facet.field': ['THREAT_TYPE']})
        # [u'1', 25662, u'2', 16844, u'4', 3503, u'0', 639, u'3', 29]
        _values = threat_types_result.facets['facet_fields']['THREAT_TYPE']
        threat_types = defaultdict(lambda: 0, zip(_values[0::2], _values[1::2]))
    except:
        threat_types = defaultdict(lambda: 0, zip([str(i) for i in range(7)], [0] * 7))

    try:
        waf_attacks = waf_solr.search('*:*').hits
    except:
        waf_attacks = 0

    try:
        tda_attacks = tda_solr.search('*:*').hits
    except:
        tda_attacks = 0

    try:
        ids_attacks = ids_solr.search('*:*').hits
    except:
        ids_attacks = 0
    all_attacks = tda_attacks + waf_attacks + ids_attacks

    # 0: Malicious content
    # 1: Malicious behavior
    # 2: Suspicious behavior
    # 3: Exploit
    # 4: Grayware
    # 5: Malicious URLs
    # 6: Disruptive Applications
    # 7: 全攻击量:waf + TDA + IDS攻击量
    # 8: WAF攻击量
    # 9: TDA攻击量
    # 10:IDS攻击量
    values = zip([today] * 11, [str(i) for i in range(11)],
                 [threat_types[str(i)] for i in range(7)] + [all_attacks, waf_attacks, tda_attacks, ids_attacks])

    conn = pymysql.connect(host='10.15.42.21', port=3306, user='root', passwd='root', db='traffic')
    cur = conn.cursor()
    cur.executemany('insert into predict(ThreatDate, ThreatType, ThreatNumber) values(%s, %s, %s)', values)
    conn.commit()
    cur.close()
    conn.close()


def update_uuid1(id0, uuid1):
    doc = [{"id": id0, "RelationUUID_s": uuid1}]
    tda_solr.add(doc, fieldUpdates={"RelationUUID_s": "set"})


def update_uuid(r0, uuid1):
    # TODO: limit time interval
    if r0['RelationUUID_s'] != '0':
        return

    doc = [{"id": r0['id'], "RelationUUID_s": uuid1}]
    tda_solr.add(doc, fieldUpdates={"RelationUUID_s": "set"})


def set_pattack(tda_solr, value='0', attack_phase=aps[1]):
    results = tda_solr.search('ATTACK_STAGE:{}'.format(attack_phase), rows=10000)
    for r in results:
        doc = [{"id": r['id'], "RelationUUID_s": value}]
        tda_solr.add(doc, fieldUpdates={"RelationUUID_s": "set"})


def solr_search(ap, direction, RelationUUID=0):
    fq = ['ATTACK_STAGE:{}'.format(ap), 'direction_s:{}'.format(direction)]
    if RelationUUID == 0:
        fq.append('RelationUUID_s:0')
    results = tda_solr.search('*:*', fq=fq, rows=10000)
    # print ap, results.hits
    return results


def apt_relate(tda_solr):
    start = 0
    for r01 in solr_search(aps[1], 0, 1):
        uuid1 = r01['RelationUUID_s']
        # phase0 < --->phase1
        for r00 in solr_search(aps[0], 0):  # results0[0]:
            if r00['DST_IP'] == r01['DST_IP']:
                update_uuid(r00, uuid1)

        # phase1 < --->phase2
        for r02 in solr_search(aps[2], 0):  # for r02 in results0[2]:
            print r02['DST_IP'], r01['DST_IP'], 1, r02['RelationUUID_s'], r01['RelationUUID_s']
            if r02['DST_IP'] == r01['DST_IP']:
                update_uuid(r02, uuid1)
                # print r02['id'], r01['RelationUUID_s'], r02['RelationUUID_s']

                # phase2 < --->phase3
                for r13 in solr_search(aps[3], 1):  # for r13 in results1[3]:
                    print r13['DST_IP'], r02['DST_IP'], 11, r13['RelationUUID_s'], r02['RelationUUID_s']
                    if r13['DST_IP'] == r02['DST_IP']:
                        update_uuid(r13, uuid1)

                        # phase3 < --->phase4
                        for r04 in solr_search(aps[4], 0):  # for r04 in results0[4]:
                            print r04['DST_IP'], r13['DST_IP'], 111, r04['RelationUUID_s'], r13['RelationUUID_s']
                            if r04['DST_IP'] == r13['DST_IP'] or r04['DST_IP'] == r13['SRC_IP']:
                                update_uuid(r04, uuid1)

    for r11 in solr_search(aps[1], 1, 1):  # results1[1]:
        uuid1 = r11['RelationUUID_s']
        for r00 in solr_search(aps[0], 0):  # results0[0]:
            if r00['DST_IP'] == r11['SRC_IP']:
                update_uuid(r00, uuid1)

        for r02 in solr_search(aps[2], 0):  # results0[2]:
            print r02['DST_IP'], r11['SRC_IP'], 2
            if r02['DST_IP'] == r11['SRC_IP']:
                update_uuid(r02, uuid1)

                for r13 in solr_search(aps[3], 1):  # results1[3]:
                    if r13['DST_IP'] == r02['DST_IP']:
                        update_uuid(r13, uuid1)

                        for r04 in solr_search(aps[4], 0):  # results0[4]:
                            if r04['DST_IP'] == r13['DST_IP'] or r04['DST_IP'] == r13['SRC_IP']:
                                update_uuid(r04, uuid1)

    for r01 in solr_search(aps[1], 0, 1):  # results0[1]:
        uuid1 = r01['RelationUUID_s']
        for r10 in solr_search(aps[0], 1):  # results1[0]:
            if r10['SRC_IP'] == r01['DST_IP']:
                update_uuid(r10, uuid1)

        for r12 in solr_search(aps[2], 1):  # results1[2]:
            print r12['SRC_IP'], r01['DST_IP'], 3
            if r12['SRC_IP'] == r01['DST_IP']:
                update_uuid(r12, uuid1)

                for r13 in solr_search(aps[3], 1):  # results1[3]:
                    if r13['DST_IP'] == r12['SRC_IP']:
                        update_uuid(r13, uuid1)

                        for r04 in solr_search(aps[4], 0):  # results0[4]:
                            if r04['DST_IP'] == r13['DST_IP'] or r04['DST_IP'] == r13['SRC_IP']:
                                update_uuid(r04, uuid1)

    for r11 in solr_search(aps[1], 1, 1):  # results1[1]:
        uuid1 = r11['RelationUUID_s']
        for r10 in solr_search(aps[0], 1):  # results1[0]:
            if r10['SRC_IP'] == r11['SRC_IP']:
                update_uuid(r10, uuid1)

        for r12 in solr_search(aps[2], 1):  # results1[2]:
            print r12['SRC_IP'], r11['SRC_IP'], 4
            if r12['SRC_IP'] == r11['SRC_IP']:
                update_uuid(r12, uuid1)

                for r13 in solr_search(aps[3], 1):  # results1[3]:
                    if r13['DST_IP'] == r12['SRC_IP']:
                        update_uuid(r13, uuid1)

                        for r04 in solr_search(aps[4], 0):  # results0[4]:
                            if r04['DST_IP'] == r13['DST_IP'] or r04['DST_IP'] == r13['SRC_IP']:
                                update_uuid(r04, uuid1)

    while True:
        uuid0_results = tda_solr.search('RelationUUID_s:0', start=start, rows=1000)
        start += len(uuid0_results)
        if len(uuid0_results) == 0:
            break
        for r in uuid0_results:
            if (datetime.now() - datetime.strptime(r['logTime_dt'],
                                                   "%Y-%m-%dT%H:%M:%SZ")).seconds > 24 * 60 * 60:
                update_uuid1(r['id'], '1')


if __name__ == '__main__':
    # ip_addr = 'http://10.15.42.19:8181'
    ip_addr = 'http://10.21.17.207:8181'
    time_now = datetime.now()
    today = datetime.now().strftime('%Y%m%d')
    tda_solr = Solr('{0}/solr/tda_{1}'.format(ip_addr, today))
    # tda_solr.delete(q='*:*')
    # set_pattack(tda_solr)
    # apt_relate(tda_solr)

    while True:
        try:
            time_now = datetime.now()
            today = time_now.strftime('%Y%m%d')
            yesterday = (time_now - timedelta(days=1)).strftime('%Y%m%d')
            if time_now.hour == 3:
                cal_attacks(ip_addr, yesterday)
            tda_solr = Solr('{0}/solr/tda_{1}'.format(ip_addr, today))
            apt_relate(tda_solr)
            sleep(1 * 60 * 60)
        except Exception as e:
            print e
            sleep(60)
