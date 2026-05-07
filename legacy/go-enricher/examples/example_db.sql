--
-- PostgreSQL database dump
--

--
-- Name: order_1; Type: TABLE; Schema: public; Owner: demo
--

CREATE TABLE public.order_1 (
    uid text NOT NULL,
    product integer NOT NULL,
    quantity integer NOT NULL,
    date date NOT NULL
);

ALTER TABLE public.order_1 OWNER TO demo;

--
-- Name: p; Type: TABLE; Schema: public; Owner: demo
--

CREATE TABLE public.p (
    id integer NOT NULL,
    w integer,
    st text,
    nm text,
    description text,
    cat text
);

ALTER TABLE public.p OWNER TO demo;

--
-- Name: p_id_seq; Type: SEQUENCE; Schema: public; Owner: demo
--

CREATE SEQUENCE public.p_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER TABLE public.p_id_seq OWNER TO demo;

--
-- Name: p_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: demo
--

ALTER SEQUENCE public.p_id_seq OWNED BY public.p.id;

--
-- Name: users; Type: TABLE; Schema: public; Owner: demo
--

CREATE TABLE public.users (
    email text NOT NULL,
    name text NOT NULL,
    dob text,
    country text,
    state text,
    pc text,
    billing_address text,
    shipping_address text
);

ALTER TABLE public.users OWNER TO demo;

--
-- Name: p id; Type: DEFAULT; Schema: public; Owner: demo
--

ALTER TABLE ONLY public.p ALTER COLUMN id SET DEFAULT nextval('public.p_id_seq'::regclass);

--
-- Data for Name: order_1; Type: TABLE DATA; Schema: public; Owner: demo
--

INSERT INTO public.order_1 VALUES ('alice@example.com', 1, 2, '2023-01-15');
INSERT INTO public.order_1 VALUES ('alice@example.com', 3, 1, '2023-02-10');
INSERT INTO public.order_1 VALUES ('bob@example.com', 2, 1, '2023-03-05');
INSERT INTO public.order_1 VALUES ('charlie@example.com', 5, 4, '2023-03-10');

--
-- Data for Name: p; Type: TABLE DATA; Schema: public; Owner: demo
--

INSERT INTO public.p VALUES (1, 500, 'in_stock', 'Wireless Mouse', 'A compact wireless mouse with USB dongle', 'electronics');
INSERT INTO public.p VALUES (2, 1500, 'pending', 'LED Monitor', '24-inch HD monitor', 'electronics');
INSERT INTO public.p VALUES (3, 100, 'shipped', 'Notebook', 'A 200-page lined notebook for note-taking', 'stationery');
INSERT INTO public.p VALUES (4, 2000, 'cancelled', 'Winter Jacket', 'Warm jacket for cold weather', 'clothes');
INSERT INTO public.p VALUES (5, 300, 'in_stock', 'Coffee Mug', 'Ceramic mug for hot beverages', 'kitchen');


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: demo
--

INSERT INTO public.users VALUES ('alice@example.com', 'Alice', '1992-04-01', 'US', 'CA', '90001', NULL, '1234 Sunset Blvd, Los Angeles');
INSERT INTO public.users VALUES ('bob@example.com', 'Bob', '03/15/1980', 'US', 'AZ', '85001', '456 Desert Rd, Phoenix', '456 Desert Rd, Phoenix');
INSERT INTO public.users VALUES ('charlie@example.com', 'Charlie', '1979-07-30', 'US', 'NY', '10001', '789 Madison Ave, New York', '789 Madison Ave, New York');
INSERT INTO public.users VALUES ('david@example.com', 'David', '1985-12-01', 'CA', 'ON', 'M4B1B3', NULL, '99 Bloor St, Toronto');
INSERT INTO public.users VALUES ('eve@example.com', 'Eve', '1990/01/15', 'US', 'FL', '33101', '987 Miami Rd, Miami', NULL);
INSERT INTO public.users VALUES ('john.doe@example.com', 'John Doe', '1988-02-05', 'US', 'CA', '92708', NULL, '123 Orange County Rd, Orange, CA');
INSERT INTO public.users VALUES ('jane.smith@example.com', 'Jane Smith', '1980-11-20', 'US', 'CA', '92867', '456 Orange Blossom Ln, Orange, CA', '456 Orange Blossom Ln, Orange, CA');
INSERT INTO public.users VALUES ('michael.brown@example.com', 'Michael Brown', '1975-03-12', 'US', 'TX', '73301', '789 Palm St, Austin, TX', '333 2nd Ave, Dallas, TX');
INSERT INTO public.users VALUES ('lisa.jackson@example.com', 'Lisa Jackson', '1990-06-10', 'US', 'NY', '10009', NULL, '12 Broadway, New York, NY');
INSERT INTO public.users VALUES ('alex.wu@example.com', 'Alex Wu', '1979-09-01', 'US', 'CA', '92602', '99 Orange County Cir, Irvine, CA', '88 Irvine Blvd, Irvine, CA');
INSERT INTO public.users VALUES ('thomas.clark@example.com', 'Thomas Clark', '1995-01-15', 'US', 'FL', '33133', NULL, '901 Coconut Grove, Miami, FL');
INSERT INTO public.users VALUES ('fiona.miller@example.com', 'Fiona Miller', '1978-12-25', 'US', 'AZ', '85016', '111 Desert View Rd, Phoenix, AZ', '222 Desert Rose Ln, Phoenix, AZ');
INSERT INTO public.users VALUES ('tim.reed@example.com', 'Tim Reed', '1982-07-22', 'US', 'IL', '60601', NULL, '350 E Randolph St, Chicago, IL');
INSERT INTO public.users VALUES ('olivia.chen@example.com', 'Olivia Chen', '1996-04-30', 'US', 'WA', '98104', '1750 Rainier Ave, Seattle, WA', '500 Pike St, Seattle, WA');
INSERT INTO public.users VALUES ('carol.thomas@example.com', 'Carol Thomas', '1983-08-18', 'US', 'FL', '33101', NULL, '210 Miami Beach Dr, Miami, FL');
INSERT INTO public.users VALUES ('harry.wilson@example.com', 'Harry Wilson', '1975-11-11', 'US', 'CA', '92869', '10 Skyline Rd, Anaheim, CA', '55 Orange Grove Blvd, Orange, CA');
INSERT INTO public.users VALUES ('nancy.lee@example.com', 'Nancy Lee', '1998-10-05', 'US', 'GA', '30301', '90 Peach Ave, Atlanta, GA', '300 Main St, Atlanta, GA');
INSERT INTO public.users VALUES ('roger.evans@example.com', 'Roger Evans', '1971-01-30', 'US', 'NV', '89109', NULL, '111 Strip Ave, Las Vegas, NV');
INSERT INTO public.users VALUES ('michelle.davis@example.com', 'Michelle Davis', '1977-05-07', 'US', 'CA', '91709', '100 Pine St, Chino Hills, CA', '101 Orange St, Chino Hills, CA');
INSERT INTO public.users VALUES ('william.king@example.com', 'William King', '1988-09-17', 'US', 'TX', '78701', '20 Barton Springs Rd, Austin, TX', '2500 Lake Austin Blvd, Austin, TX');
INSERT INTO public.users VALUES ('emily.hughes@example.com', 'Emily Hughes', '1992-03-21', 'US', 'NY', '10003', NULL, '77 5th Ave, New York, NY');
INSERT INTO public.users VALUES ('julie.torres@example.com', 'Julie Torres', '1979-12-02', 'US', 'CA', '92801', '700 Anaheim Blvd, Anaheim, CA', '701 Harbor Rd, Anaheim, CA');
INSERT INTO public.users VALUES ('antonio.ortiz@example.com', 'Antonio Ortiz', '1986-11-11', 'US', 'CA', '92704', NULL, '990 Orange County Plaza, Santa Ana, CA');
INSERT INTO public.users VALUES ('stephanie.moore@example.com', 'Stephanie Moore', '1993-07-19', 'US', 'OH', '44101', '333 Lakeside Dr, Cleveland, OH', '425 Rock Ave, Cleveland, OH');
INSERT INTO public.users VALUES ('felix.hall@example.com', 'Felix Hall', '1974-01-03', 'US', 'NC', '28202', NULL, '400 Uptown St, Charlotte, NC');

--
-- Name: p_id_seq; Type: SEQUENCE SET; Schema: public; Owner: demo
--

SELECT pg_catalog.setval('public.p_id_seq', 5, true);

--
-- Name: p p_pkey; Type: CONSTRAINT; Schema: public; Owner: demo
--

ALTER TABLE ONLY public.p
    ADD CONSTRAINT p_pkey PRIMARY KEY (id);

--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: demo
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (email);

--
-- PostgreSQL database dump complete
--
