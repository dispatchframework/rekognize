import re

import boto3
import requests
from azure.storage.common import CloudStorageAccount


def handle(ctx, params):

    account = CloudStorageAccount(
        account_name=ctx["secrets"]["azure_account_name"],
        account_key=ctx["secrets"]["azure_account_key"])
    svc = account.create_block_blob_service()

    source = ctx["event"]["source"]
    m = re.search(r"#/blobServices/default/containers/(.+?)/blobs/(.+)$", source)
    if not m:
        return {
            "error": "could not parse source %s" % source
        }
    container, name = m.groups()

    blob = svc.get_blob_to_bytes(container_name=container, blob_name=name)

    rek = boto3.client(
        "rekognition",
        region_name="us-west-2",
        aws_access_key_id=ctx["serviceBindings"]["rekognition"]["REKOGNITION_AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=ctx["serviceBindings"]["rekognition"]["REKOGNITION_AWS_SECRET_ACCESS_KEY"])
    rek_resp = rek.detect_labels(Image={'Bytes': blob.content})


    print("Detected labels in " + name)

    fields = []
    metadata = {}
    for label in rek_resp["Labels"]:
        metadata[label["Name"].replace(" ", "")] = str(label["Confidence"])
        fields.append({
            "title": label["Name"],
            "value": label["Confidence"],
            "short": True
        })

    svc.create_blob_from_bytes(
        "dispatchpubliccontainer", blob.name, blob.content, metadata=metadata)

    print("Done... %s" % metadata)

    message = {
        "attachments": [
            {
                "text": "File %s just pushed to %s" % (name, container),
                "fields": fields,
                "image_url": "https://%s.blob.core.windows.net/dispatchpubliccontainer/%s" % (ctx["secrets"]["azure_account_name"], name),
                "color": "#F35A00"
            }
        ]
    }

    requests.post(ctx["secrets"]["webhook-url"], json=message)
    return message


