CREATE TABLE t_addr (
    a_id integer NOT NULL,
    u_id integer,
    s_addr character varying(255),
    cty character varying(100),
    st character varying(100),
    cntry character varying(100),
    pst_c character varying(20),
    is_dflt boolean,
    lbl character varying(100),
    lat numeric(10,8),
    lon numeric(11,8),
    phn character varying(20),
    c_nm character varying(100),
    cmp_nm character varying(100),
    apt_num character varying(50),
    bld_nm character varying(100),
    flr_num character varying(50),
    gt_c character varying(50),
    d_inst text,
    a_typ character varying(50),
    c_dt timestamp without time zone,
    u_dt timestamp without time zone
);

CREATE TABLE t_brnd (
    b_id integer NOT NULL,
    b_nm character varying(255),
    desc text,
    w_url character varying(255),
    l_url character varying(255),
    is_act boolean,
    c_dt timestamp without time zone,
    u_dt timestamp without time zone
);

CREATE TABLE t_cmp (
    cmp_id integer NOT NULL,
    cmp_nm character varying(255),
    dur integer,
    s_dt date,
    e_dt date
);

CREATE TABLE t_crt (
    crt_id integer NOT NULL,
    u_id integer,
    p_id integer,
    qty integer,
    a_dt timestamp without time zone
);

CREATE TABLE t_cat (
    c_id integer NOT NULL,
    p_c_id integer,
    c_nm character varying(255),
    desc text,
    i_url character varying(255),
    is_act boolean,
    c_dt timestamp without time zone,
    u_dt timestamp without time zone,
    m_ttl character varying(255),
    m_desc text,
    slg character varying(255),
    d_ord integer,
    lvl integer,
    pth character varying(255),
    l_val integer,
    r_val integer
);

CREATE TABLE t_cpn (
    cpn_id integer NOT NULL,
    c_cde character varying(255),
    d_amt numeric(10,2),
    d_typ character varying(50),
    min_sp numeric(10,2),
    max_sp numeric(10,2),
    s_dt timestamp without time zone,
    e_dt timestamp without time zone,
    is_act boolean,
    c_dt timestamp without time zone,
    u_dt timestamp without time zone
);

CREATE TABLE t_ord_itm (
    oi_id integer NOT NULL,
    o_id integer,
    u_id integer,
    o_dt timestamp without time zone,
    t_amt numeric(10,2),
    sts character varying(100),
    p_mthd character varying(100),
    s_mthd character varying(100),
    s_a_id integer,
    b_a_id integer,
    p_sts character varying(100),
    d_sts character varying(100),
    d_dt date,
    c_rsn character varying(255),
    c_dt timestamp without time zone,
    p_id integer
);

CREATE TABLE t_ord (
    o_id integer NOT NULL,
    u_id integer,
    o_dt timestamp without time zone,
    t_amt numeric(10,2),
    sts character varying(100),
    p_mthd character varying(100),
    s_mthd character varying(100),
    s_a_id integer,
    b_a_id integer,
    r_req boolean,
    r_app boolean,
    r_rej boolean,
    rf_prc boolean,
    rf_cmp boolean,
    cmp_id integer
);

CREATE TABLE t_pay (
    pay_id integer NOT NULL,
    o_id integer,
    p_dt timestamp without time zone,
    amt numeric(10,2),
    p_mthd character varying(100),
    p_sts character varying(100),
    tx_id character varying(255),
    a_cde character varying(255),
    curr character varying(3),
    pg_rsp text,
    p_nts text
);

CREATE TABLE t_prd (
    p_id integer NOT NULL,
    c_id integer,
    b_id integer,
    p_nm character varying(255),
    prc numeric(10,2),
    d_prc numeric(10,2),
    stk_qty integer,
    is_ftr boolean,
    is_act boolean,
    c_dt timestamp without time zone,
    u_dt timestamp without time zone,
    wgt numeric(10,2),
    len numeric(10,2),
    wid numeric(10,2),
    hgt numeric(10,2),
    clr character varying(100),
    sz character varying(50),
    mat character varying(100),
    wrnt character varying(255),
    o_cntry character varying(100),
    mpn character varying(100),
    sku character varying(100),
    bcd character varying(100),
    tgs text,
    rtg numeric(3,2),
    t_rev integer,
    is_dsc boolean,
    d_pct numeric(5,2),
    min_o_qty integer,
    max_o_qty integer,
    l_time integer,
    a_sts character varying(50),
    slg character varying(255),
    slr_id integer
);

CREATE TABLE t_rfnd (
    rf_id integer NOT NULL,
    o_id integer,
    u_id integer,
    r_amt numeric(10,2),
    r_mthd character varying(255),
    r_sts character varying(255),
    r_dt timestamp without time zone,
    nts text
);

CREATE TABLE t_rtn_req (
    r_id integer NOT NULL,
    o_id integer,
    u_id integer,
    r_rsn text,
    r_sts character varying(100),
    r_dt timestamp without time zone,
    r_nts text,
    rs_dt timestamp without time zone
);

CREATE TABLE t_rev (
    rev_id integer NOT NULL,
    u_id integer,
    p_id integer,
    rtg integer,
    rev_dt timestamp without time zone,
    rev_txt text,
    is_app boolean,
    a_dt timestamp without time zone
);

CREATE TABLE t_shp (
    s_id integer NOT NULL,
    o_id integer,
    s_dt timestamp without time zone,
    e_d_dt timestamp without time zone,
    a_d_dt timestamp without time zone,
    c_nm character varying(255),
    t_num character varying(255),
    s_cst numeric(10,2),
    s_mthd character varying(255),
    s_a_id integer,
    u_id integer
);

CREATE TABLE t_usr (
    u_id integer NOT NULL,
    u_nm character varying(255),
    eml character varying(255),
    pwd character varying(255),
    f_nm character varying(100),
    l_nm character varying(100),
    dob date,
    gndr gndr_enm,
    phn character varying(20),
    pp_url character varying(255),
    cp_url character varying(255),
    bio text,
    w_url character varying(255),
    r_dt timestamp without time zone,
    l_l_dt timestamp without time zone,
    is_act boolean,
    is_adm boolean,
    is_vrf boolean,
    v_cde character varying(100),
    v_e_dt timestamp without time zone,
    f_log_a integer,
    l_fl_dt timestamp without time zone,
    a_lck_dt timestamp without time zone,
    a_lck_rsn character varying(255),
    s_addr character varying(255),
    cty character varying(100),
    st character varying(100),
    cntry character varying(100),
    pst_c character varying(20),
    sq1 character varying(255),
    sa1 character varying(255),
    sq2 character varying(255),
    sa2 character varying(255),
    l_pwd_dt timestamp without time zone,
    e_v_sts boolean,
    p_v_sts boolean,
    p_lang character varying(50),
    tz character varying(50),
    occ character varying(100),
    int text,
    edu character varying(100),
    r_sts character varying(50),
    rl_id integer
);

CREATE TABLE t_wsh (
    w_id integer NOT NULL,
    u_id integer,
    p_id integer,
    a_dt timestamp without time zone
);