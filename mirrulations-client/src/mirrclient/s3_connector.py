import json
import boto3


class AWSConnector():

    def __init__(self):
        try:
            self.session = boto3.Session(profile_name="profile_name")
            self.s_3 = self.session.client("s3")
        except Exception:
            print("Something wrong happened")

    # Credentials folder is still missing such as ~/.aws/credentials
    def check_for_s3_connection(self):
        """
        Checks if a valid connection could be made to s3
        """

        try:
            connection = self.s_3.listBuckets()
            return connection["ResponseMetadata"]["HTTPStatusCode"] == 200
        except Exception:
            return False

    def put_results_s3(self, data, output_path, bucket_name):
        """
        Puts the job results in an s3 bucket.
        Parameters
        ----------
        job : dict
            results of the job
        job_result : dict
            states of the job failed
        bucket_name : str
            name of the bucket
        """

        self.s_3.put_object(Bucket=bucket_name,
                            Key=output_path, Body=json.dumps(data))
