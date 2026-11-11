"""AuthStack: one Cognito user pool for everyone (customers, owners, cashiers).

sumaat-users  email + password, email confirmed with a code at sign-up. Required: email, name, phone.
Groups decide what a user can do (the frontend shows pages by group, the API enforces it):
  customer  every self-signup (owners too: an owner can also order food with the same account)
  owner     self-signup who chose "I own a restaurant" (custom:signupRole = owner)
  cashier   created by an owner (Step 5)
"""

from pathlib import Path

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from cdk_nag import NagSuppressions
from constructs import Construct

FUNCTIONS_DIR = Path(__file__).resolve().parent.parent / "functions"
RUNTIME = lambda_.Runtime.PYTHON_3_14
GROUPS = ("customer", "owner", "cashier")


class AuthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.user_pool = cognito.UserPool(
            self,
            # New pool (replaces BusinessPoolV2 + CustomerPool): a required attribute (phone) can't be
            # added to an existing pool, so CloudFormation must create a new one.
            "UsersPool",
            user_pool_name="sumaat-users",
            feature_plan=cognito.FeaturePlan.ESSENTIALS,
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),  # 6-digit code by email (Cognito's sender)
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
                fullname=cognito.StandardAttribute(required=True, mutable=True),  # Cognito "name" = full name
                phone_number=cognito.StandardAttribute(required=True, mutable=True),  # contact only, not verified
            ),
            custom_attributes={
                "restaurantId": cognito.StringAttribute(mutable=True),
                "signupRole": cognito.StringAttribute(mutable=True, max_len=20),  # "customer" | "owner"
            },
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            mfa=cognito.Mfa.OFF,
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,
        )

        for group in GROUPS:
            cognito.CfnUserPoolGroup(
                self,
                f"{group.capitalize()}Group",
                user_pool_id=self.user_pool.user_pool_id,
                group_name=group,
            )

        self.client = self.user_pool.add_client(
            "WebClient",
            user_pool_client_name="web",
            generate_secret=False,
            # SRP: what Amplify uses in the browser. USER_PASSWORD: lets scripts/get_token.py log in from the
            # terminal for testing (password goes to Cognito over HTTPS).
            auth_flows=cognito.AuthFlow(user_srp=True, user_password=True),
            prevent_user_existence_errors=True,
            read_attributes=cognito.ClientAttributes()
            .with_standard_attributes(email=True, email_verified=True, fullname=True, phone_number=True)
            .with_custom_attributes("restaurantId", "signupRole"),
            # restaurantId is deliberately NOT writable: only the API sets it (Admin APIs).
            write_attributes=cognito.ClientAttributes()
            .with_standard_attributes(email=True, fullname=True, phone_number=True)
            .with_custom_attributes("signupRole"),
        )

        post_confirmation = lambda_.Function(
            self,
            "PostConfirmationFn",
            runtime=RUNTIME,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.handler",
            code=lambda_.Code.from_asset(str(FUNCTIONS_DIR / "post_confirmation")),
            timeout=Duration.seconds(5),
            memory_size=256,
            log_group=logs.LogGroup(
                self,
                "PostConfirmationFnLogs",
                retention=logs.RetentionDays.ONE_MONTH,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )
        self.user_pool.add_trigger(cognito.UserPoolOperation.POST_CONFIRMATION, post_confirmation)

        # Separate Policy + wildcard pool ARN: referencing user_pool.user_pool_arn here
        # would create a pool <-> Lambda circular dependency.
        post_confirmation.role.attach_inline_policy(
            iam.Policy(
                self,
                "PostConfirmationPolicy",
                statements=[
                    iam.PolicyStatement(
                        actions=["cognito-idp:AdminAddUserToGroup"],
                        resources=[f"arn:aws:cognito-idp:{self.region}:{self.account}:userpool/*"],
                    )
                ],
            )
        )

        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=self.client.user_pool_client_id)

        self._suppress_nag()

    def _suppress_nag(self) -> None:
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-COG2",
                    "reason": "POC decision: no MFA. Users sign in with email + password; the email is "
                    "verified with a code at sign-up.",
                },
                {
                    "id": "AwsSolutions-COG3",
                    "reason": "Threat protection (AdvancedSecurityMode ENFORCED) requires the Cognito "
                    "Plus plan; this POC uses Essentials.",
                },
                {
                    "id": "AwsSolutions-COG8",
                    "reason": "Plus plan not justified for a one-week POC with demo traffic; "
                    "Essentials covers our sign-in needs. Revisit for production.",
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Lambda role uses the AWS-managed AWSLambdaBasicExecutionRole "
                    "(CloudWatch Logs only); acceptable for the POC.",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
                    ],
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Post-confirmation trigger uses a wildcard pool ARN (this account + region "
                    "only) to avoid a user pool <-> Lambda circular dependency.",
                    "appliesTo": [{"regex": "/^Resource::arn:aws:cognito-idp:.+:userpool\\/\\*$/"}],
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Python 3.14 is pinned project-wide (.python-version) so local tests "
                    "match the Lambda runtime; upgrade together later.",
                },
            ],
        )
