import os
import signal
import subprocess

import boto3
import git
from boto3.dynamodb.types import TypeDeserializer


def scan_dynamodb_table(client, table_name):
    results = []
    last_evaluated_key = None
    while True:
        if last_evaluated_key:
            response = client.scan(TableName=table_name, ExclusiveStartKey=last_evaluated_key)
        else:
            response = client.scan(TableName=table_name)

        last_evaluated_key = response.get('LastEvaluatedKey')
        results.extend(response['Items'])

        if not last_evaluated_key:
            break
    return results


def dynamodb_json_to_dictionary(item):
    deserializer = TypeDeserializer()
    return {key: deserializer.deserialize(value=value) for key, value in item.items()}


def execute_shell_command(command, timeout=None):
    process = subprocess.Popen(command,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True, shell=True)
    try:
        output = process.communicate(timeout=timeout)
        timeout_reached = False
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        output = process.communicate()
        timeout_reached = True
    return process.returncode, timeout_reached, output[0].decode('utf-8')


def deploy_lambda(zip_file_name, aws_lambda_function_name, aws_lambda_region):
    lambda_deploy_return_code = execute_shell_command(
        f'aws lambda update-function-code --function-name {aws_lambda_function_name} --region {aws_lambda_region} --zip-file fileb://{zip_file_name}.zip')

    assert lambda_deploy_return_code[0] == 0, lambda_deploy_return_code[2]


github_token = os.environ.get('github_token')
dev_region = os.environ.get('dev_region')
beta_region = os.environ.get('beta_region')
prod_region = os.environ.get('prod_region')
dynamodb_table_name = os.environ.get('metadata_table')
dynamodb_client = boto3.client('dynamodb')

dynamodb_data = scan_dynamodb_table(dynamodb_client, dynamodb_table_name)

for dynamodb_item in dynamodb_data:
    item_dictionary = dynamodb_json_to_dictionary(dynamodb_item)

    repo_url = item_dictionary.get("repoUrl")
    print(f'start processing {repo_url} repository')
    assert repo_url, 'repo_url must no be null'

    # get the latest commit hash for each tag
    latest_commit_hash_dev = str(item_dictionary.get("latestCommitHashDev") or '')
    latest_commit_hash_beta = str(item_dictionary.get("latestCommitHashBeta") or '')
    latest_commit_hash_prod = str(item_dictionary.get("latestCommitHashProd") or '')

    repo_cloning_url = repo_url.replace('https://', f'https://oauth2:{github_token}@') + '.git'
    repo_name = repo_url[repo_url.rindex('/') + 1:]
    repo = git.Repo.clone_from(repo_cloning_url, repo_name)

    target_commit_hash_dev = repo.git.rev_parse('HEAD')
    target_commit_hash_beta = ''
    target_commit_hash_prod = ''

    # looking for latest commit hash for each tag
    for tag in reversed(repo.tags):
        if not str(target_commit_hash_beta) and str(tag.name).startswith('beta'):
            target_commit_hash_beta = repo.commit(tag).hexsha
        elif not str(target_commit_hash_prod) and str(tag.name).startswith('prod'):
            target_commit_hash_prod = repo.commit(tag).hexsha
        if str(target_commit_hash_prod) and str(target_commit_hash_beta):
            break

    lambda_zip_return_code = execute_shell_command(f'zip -r -j {repo_name}.zip {repo_name}/lambda/*')
    assert lambda_zip_return_code[0] == 0, lambda_zip_return_code[2]

    print('------------------------------------------------------')
    print(f'deploy stage for repo {repo_name}')

    anything_to_deploy = False

    if latest_commit_hash_dev != target_commit_hash_dev:
        print(f'deploy dev {repo_name}')
        deploy_lambda(repo_name, 'dev-' + repo_name, dev_region)
        anything_to_deploy = True

    if latest_commit_hash_beta != target_commit_hash_beta:
        print(f'deploy beta {repo_name}')
        deploy_lambda(repo_name, 'beta-' + repo_name, beta_region)
        anything_to_deploy = True

    if latest_commit_hash_prod != target_commit_hash_prod:
        print(f'deploy prod {repo_name}')
        deploy_lambda(repo_name, 'prod-' + repo_name, prod_region)
        anything_to_deploy = True

    if anything_to_deploy:
        print('------------------------------------------------------')
        print('update dynamodb stage')
        dynamodb_client.put_item(TableName=dynamodb_table_name, Item={'repoUrl': {'S': repo_url},
                                                                      'latestCommitHashDev': {
                                                                          'S': target_commit_hash_dev},
                                                                      'latestCommitHashBeta': {
                                                                          'S': target_commit_hash_beta},
                                                                      'latestCommitHashProd': {
                                                                          'S': target_commit_hash_prod}})
    else:
        print(f'nothing to deploy for repo {repo_name}')
