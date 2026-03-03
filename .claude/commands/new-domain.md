# Create a New Domain

Set up the standard folder scaffold for a new domain so it's ready for policy document ingestion and rule extraction.

## Input

```
/new-domain <domain>
```

If `<domain>` is not provided, prompt: "What should the domain be named? (e.g., `snap`, `ak_doh`)"

## Pre-flight

1. **Domain name provided?** — If not, prompt for it. Then continue.

2. **Domain folder already exists?**
   - YES → Print:
     ```
     Domain already exists: domains/<domain>/
     To extract rulesets: /extract-ruleset <domain>
     ```
     Then stop.

## Process

### Step 1: Create folder structure

Create the following directories:

```
domains/<domain>/input/policy_docs/
domains/<domain>/specs/
domains/<domain>/output/
domains/<domain>/demo/
```

Also create a stub demo script at `domains/<domain>/demo/start.sh`:

```bash
#!/usr/bin/env bash
# Demo script for <domain>
# TODO: implement a sample OPA query against the running server
# Example:
#   curl -s http://localhost:8181/v1/data/<domain>/eligibility/decision -d @- <<'EOF'
#   { "input": { "household_size": 3, "gross_monthly_income": 1800 } }
#   EOF
echo "No demo implemented yet for <domain>."
```

Print the created structure:

```
Created domains/<domain>/
  input/policy_docs/    ← add .md policy documents here
  specs/
  output/
  demo/
    start.sh            ← stub demo script (edit to add sample queries)
```

### Step 2: Print next steps

```
Domain '<domain>' is ready.

Next steps:
  1. Add .md policy documents to domains/<domain>/input/policy_docs/
  2. Run /index-inputs <domain> to build a document index
  3. Run /refine-guidance <domain> to set extraction goals
  4. Run /extract-ruleset <domain> to extract the CIVIL ruleset
  5. Run /create-tests <domain> to draft the test suite
  6. Run /transpile-and-test <domain> to compile to Rego and validate
```

## Common Mistakes to Avoid

- Do not use this command if the domain folder already exists — the scaffold is a one-time setup
- Domain names must be valid directory names: lowercase letters, digits, underscores, no spaces (e.g., `snap`, `ak_doh`, `ca_calworks`)
