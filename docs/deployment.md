# Azure deployment

Deployed by hand for now. Automatic deployment comes in M8. Replace names in `<...>` with your own.
Set a budget alert before creating anything: it warns you, but does not stop spending.

## What was created (UK South)

| Resource | Settings |
| --- | --- |
| Storage account | Standard LRS, no public blobs, shared keys disabled, TLS 1.2 |
| User-assigned managed identity | Used for storage, deployment and logs |
| Log Analytics and Application Insights | 0.1 GB daily cap, 30 days kept |
| Function App (Flex Consumption) | Python 3.13, 512 MB, at most 1 instance, none always ready |

The identity's roles on the storage account: Storage Blob Data Owner, Storage Queue Data Contributor,
Storage Queue Data Message Sender, Storage Table Data Contributor. On Application Insights: Monitoring
Metrics Publisher.

## App settings

| Name | Value |
| --- | --- |
| `AzureWebJobsStorage__accountName` | `<storage account>` |
| `AzureWebJobsStorage__credential` | `managedidentity` |
| `AzureWebJobsStorage__clientId` | `<identity client id>` |
| `APPLICATIONINSIGHTS_AUTHENTICATION_STRING` | `ClientId=<identity client id>;Authorization=AAD` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Added by Azure |
| `STRIPE_WEBHOOK_SECRET` | From the Stripe sandbox endpoint, entered in the portal |

Delete the `AzureWebJobsStorage` setting that Azure adds, because shared keys are disabled.

## Deploy

Copy `function_app.py`, `host.json`, `requirements.txt` and `order_sync/*.py` to an empty folder, then
run this there with a Python 3.13 environment active:

    func azure functionapp publish <function app> --python --build remote

The clean folder is deliberate: with Core Tools 4.17.0, `--list-included-files` listed files that
`.funcignore` excludes, so the list could not be used to check what would be uploaded.

## Problem: every second request returned 503

With one instance, requests alternated between a fast reply and a 503 after 60 seconds. A restart did
not help. With two instances, every third request failed, so successes matched the instance count.
Setting HTTP concurrency to 10 stopped the failures, with the limit back at one instance:

    az functionapp scale config set -g <group> -n <function app> --maximum-instance-count 1 --trigger-type http --trigger-settings perInstanceConcurrency=10

Why Azure kept treating an instance as busy is not known.

## Checked

- A Stripe sandbox checkout was accepted (200) and one message appeared on the `orders` queue.
- The order ID in the logs matched Stripe's. Unsigned requests were rejected (400).
- Open question: the logs had two "request stream was aborted" exceptions, cause unknown.

## Remove everything

    az group delete --name <group>

Delete the Stripe sandbox endpoint too.
