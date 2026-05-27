-- Table `employee`: The core table for employee profiles, names, and hire dates.
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

-- Table `department`: Required to answer questions about which department an employee belongs to.
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


-- Table `job`: Required to answer questions regarding job titles and roles.
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


-- Table `leave_request`: Required to handle queries about sick leave, vacation, and time off.
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


-- Table `employee_certification`: Specifically called out in the Query Data Tool description for handling certification questions.
CREATE TABLE employee_certification (
    certification_id integer NOT NULL,
    employee_id integer,
    certification_name character varying(255),
    issuing_organization character varying(255),
    issue_date date,
    expiration_date date
);

-- Table `salary`: Required for general salary lookup (base compensation), acting as the bridge before a user needs to escalate to the separate Payroll Tool for detailed gross pay, net pay, and tax statements.
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