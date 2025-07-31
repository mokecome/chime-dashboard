import pymysql
# **資料庫的 DB 連線設定**
DB_CONFIG_CHAT = {
    "host": "eksdb.cluster-cmaiezmmaayo.ap-northeast-1.rds.amazonaws.com",
    "user": "mike",
    "password": "qEsudqgCFgdp",
    "database": "taiwan",
    "port": 3306,
    "charset": "utf8mb4",
}

def fetch_stamp_data(USER_ID:str):
    try:
        connection = pymysql.connect(**DB_CONFIG_CHAT)
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        sql_query = """
       SELECT
        sn.code AS code,
        sai.name AS activity_name,
        pi.name AS stamp_name,
        COALESCE(sm.location, sn.location) AS stamp_address,
        COALESCE(sg.latitude, sm.latitude) AS latitude,  
        COALESCE(sg.longitude, sm.longitude) AS longitude,
        sm.store_name AS store_name,
        FROM_UNIXTIME(sn.start_time, '%Y-%m-%d') AS s_time,
        FROM_UNIXTIME(sn.end_time, '%Y-%m-%d') AS e_time
        FROM
        seal_nft sn
        LEFT JOIN seal_map sm ON sn.id = sm.seal_nft_id
        LEFT JOIN seal_gps sg ON sn.id = sg.seal_id
        JOIN seal_activity sa ON sn.activity_id = sa.id
        JOIN seal_activity_introduction sai ON sa.id = sai.list_id
        JOIN product_introduction pi ON sn.product_id = pi.product_id
        WHERE
        sn.start_time <= UNIX_TIMESTAMP(CURRENT_DATE)
        AND sn.end_time >= UNIX_TIMESTAMP(CURRENT_DATE)
        AND sai.language = 'tw'
        AND pi.language = 'tw'
        AND sn.product_id NOT IN (
            SELECT DISTINCT tb.product_id
            FROM token_basic tb
            WHERE
            tb.owner = '${USER_ID}'
            AND tb.class = 1
        );
        """

        cursor.execute(sql_query)
        result = cursor.fetchall()
        cursor.close()
        connection.close()

        return result

    except Exception as e:
        print(f"❌ 錯誤: 無法從 `` 獲取數據 - {e}")
        return 



if __name__=='main':
    print(fetch_stamp_data(USER_ID='2'))
