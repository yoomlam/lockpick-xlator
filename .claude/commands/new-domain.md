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
     ```
     Then go to Step 2.

## Process

### Step 1: Create folder structure

Create the following directories:

```
domains/<domain>/input/policy_docs/
domains/<domain>/specs/
domains/<domain>/output/
```

Print the created structure:

```
Created domains/<domain>/
  input/policy_docs/    ← add .md policy documents here
  specs/
  output/               ← generated .rego files and demo-<module>/ dirs go here
```

### Step 2: Print next steps

```
Domain '<domain>' is ready.

Next steps:
  1. Add .md policy documents to domains/<domain>/input/policy_docs/
  2. Run /index-inputs <domain> to build a document index
  3. Run /refine-guidance <domain> to set extraction goals
  4. Run /extract-ruleset <domain> to extract the CIVIL ruleset

  5. Add/update .md policy documents to domains/<domain>/input/policy_docs/
  6. Run /update-ruleset <domain> to update the CIVIL ruleset

  7. Run /create-tests <domain> to draft the test suite
  8. Run /transpile-and-test <domain> to compile to default output language (Rego) and validate
  9. Run /create-demo <domain> to generate a browser demo
```

## Common Mistakes to Avoid

- Domain names must be valid directory names: lowercase letters, digits, underscores, no spaces (e.g., `snap`, `ak_doh`, `ca_calworks`)
