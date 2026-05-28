CREATE TABLE allowances (
    allowance_id integer NOT NULL,
    allowance character varying(255),
    allowance_description text
);

CREATE TABLE attendance (
    attendance_id integer NOT NULL,
    employee_id integer,
    date date,
    check_in_time time without time zone,
    check_out_time time without time zone,
    check_in_location character varying(255),
    check_out_location character varying(255),
    check_in_method character varying(50),
    check_out_method character varying(50),
    work_hours numeric(10,2),
    overtime_hours numeric(10,2),
    shift character varying(50),
    notes text
);

CREATE TABLE benefit (
    benefit_id integer NOT NULL,
    benefit_name character varying(255),
    description text,
    coverage character varying(255),
    provider character varying(255),
    start_date date,
    end_date date,
    eligibility_criteria jsonb,
    usage_instructions text,
    contact_info character varying(255)
);

CREATE TABLE company (
    company_id integer NOT NULL,
    company_name character varying(255),
    industry character varying(255),
    size character varying(50),
    location character varying(255),
    website character varying(255),
    contact_person character varying(255),
    contact_email character varying(255),
    contact_phone character varying(20),
    founded_date date,
    ownership_type character varying(50),
    social_media_facebook character varying(255),
    social_media_instagram character varying(255),
    social_media_linkedin character varying(255),
    social_media_x character varying(255),
    clients jsonb,
    products jsonb,
    partners jsonb,
    competitors jsonb,
    financial_year_end date
);

CREATE TABLE department (
    department_id integer NOT NULL,
    department_name character varying(255),
    manager_id integer,
    budget numeric(15,2),
    start_date date,
    end_date date,
    is_active boolean,
    goals jsonb,
    achievements jsonb,
    company_id integer
);

CREATE TABLE employee (
    employee_id integer NOT NULL,
    first_name character varying(255),
    last_name character varying(255),
    email character varying(255),
    phone_number character varying(20),
    address jsonb,
    image_url character varying(255),
    date_of_birth date,
    gender character varying(10),
    marital_status character varying(20),
    national_identification character varying(50),
    bank_account_number jsonb,
    emergency_contact_name character varying(255),
    emergency_contact_number character varying(20),
    contract_type character varying(50),
    hire_date date,
    department_id integer,
    job_id integer,
    manager_id integer,
    company_id integer
);

CREATE TABLE employee_allowances (
    employee_allowance_id integer NOT NULL,
    employee_id integer,
    allowance_id integer,
    type character varying(255),
    amount numeric(15,2),
    effective_date date,
    date_created date
);

CREATE TABLE employee_business_expense (
    expense_id integer NOT NULL,
    employee_id integer,
    expense_date date,
    expense_category character varying(255),
    expense_description text,
    expense_amount numeric(15,2),
    expense_receipt character varying(255)
);

CREATE TABLE employee_certification (
    certification_id integer NOT NULL,
    employee_id integer,
    certification_name character varying(255),
    issuing_organization character varying(255),
    issue_date date,
    expiration_date date
);

CREATE TABLE employee_computer (
    computer_id integer NOT NULL,
    employee_id integer,
    computer_name character varying(255),
    serial_number character varying(255),
    model character varying(255),
    purchase_date date,
    warranty_expiry_date date,
    status character varying(50),
    assigned_date date,
    returned_date date
);

CREATE TABLE employee_termination (
    termination_id integer NOT NULL,
    employee_id integer,
    termination_date date,
    reason character varying(255),
    description text
);

CREATE TABLE employee_training (
    employee_id integer,
    training_id integer,
    start_date date,
    end_date date
);

CREATE TABLE employee_travel (
    travel_id integer NOT NULL,
    employee_id integer,
    travel_purpose character varying(255),
    travel_destination character varying(255),
    travel_start_date date,
    travel_end_date date,
    travel_expenses numeric(15,2)
);

CREATE TABLE employee_x_benefit (
    employee_id integer,
    benefit_id integer,
    start_date date,
    end_date date
);

CREATE TABLE holiday (
    date date NOT NULL,
    day character varying(255),
    occasion character varying(255),
    geographic_location character varying(255),
    city character varying(255) NOT NULL,
    project character varying(255) NOT NULL
);

CREATE TABLE invoice (
    invoice_id integer NOT NULL,
    invoice_date date,
    due_date date,
    total_amount numeric(15,2),
    employee_id integer,
    status character varying(50)
);

CREATE TABLE job (
    job_id integer NOT NULL,
    job_title character varying(255),
    job_description text,
    skills_required jsonb,
    skills_preferred jsonb,
    min_salary numeric(15,2),
    max_salary numeric(15,2),
    department_id integer,
    responsibilities text,
    benefits jsonb,
    education_requirements jsonb,
    experience_requirements jsonb,
    employment_type character varying(50),
    location character varying(255),
    vacancies integer,
    status character varying(50)
);

CREATE TABLE job_history (
    job_history_id integer NOT NULL,
    employee_id integer,
    start_date date,
    end_date date,
    job_id integer,
    department_id integer
);

CREATE TABLE leave_request (
    leave_id integer NOT NULL,
    employee_id integer,
    leave_type character varying(50),
    start_date date,
    end_date date,
    status character varying(50) DEFAULT 'Pending',
    duration numeric(10,2),
    reason text,
    approval_date date,
    rejection_date date,
    comments text,
    attachment character varying(255),
    processed_by integer
);

CREATE TABLE manager (
    manager_id integer NOT NULL,
    start_date date,
    end_date date
);

CREATE TABLE payment (
    payment_id integer NOT NULL,
    payment_date date,
    amount numeric(15,2),
    payment_method character varying(255),
    invoice_id integer
);

CREATE TABLE performance_review (
    review_id integer NOT NULL,
    employee_id integer,
    reviewer_id integer,
    review_date date,
    performance_rating numeric(5,2),
    comments text
);

CREATE TABLE salary (
    salary_id integer NOT NULL,
    employee_id integer,
    salary numeric(15,2),
    start_date date,
    end_date date,
    currency character varying(10),
    pay_frequency character varying(50),
    bonus numeric(15,2),
    taxes numeric(15,2),
    deductions numeric(15,2),
    total_compensation numeric(15,2),
    status character varying(50)
);

CREATE TABLE timesheet (
    timesheet_id integer NOT NULL,
    date date,
    working_hours numeric(10,2),
    overtime numeric(10,2),
    leave_type character varying(255)
);

CREATE TABLE timesheet_employee (
    timesheet_id integer NOT NULL,
    employee_id integer,
    month integer,
    year integer,
    fort_night1_flag boolean,
    fort_night2_flag boolean
);

CREATE TABLE training (
    training_id integer NOT NULL,
    title character varying(255),
    description text,
    date date,
    location character varying(255),
    link character varying(255),
    trainer character varying(255),
    duration numeric(10,2),
    attendance_required boolean,
    registration_deadline_date date,
    registration_link character varying(255),
    status character varying(50),
    feedback_link character varying(255),
    materials text
);