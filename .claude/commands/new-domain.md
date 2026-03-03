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

Print the created structure:

```
Created domains/<domain>/
  input/policy_docs/    ← add .md policy documents here
  specs/
  output/
  demo/
```

### Step 2: Print next steps

```
Domain '<domain>' is ready.

Next steps:
  1. Add .md policy documents to domains/<domain>/input/policy_docs/
  2. Run /index-inputs <domain> to build a document index
  3. Run /refine-guidance <domain> to set extraction goals
  4. Run /extract-ruleset <domain> to extract the CIVIL ruleset
```

## Common Mistakes to Avoid

- Do not use this command if the domain folder already exists — the scaffold is a one-time setup
- Domain names must be valid directory names: lowercase letters, digits, underscores, no spaces (e.g., `snap`, `ak_doh`, `ca_calworks`)
