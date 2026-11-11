"""AuthStack: two Cognito user pools.

sumaat-business   owners + cashiers, email + password (SRP), email confirmed once at sign-up.
sumaat-customers  customers, phone + OTP through custom-auth triggers (OTP_MODE fixed|sms).
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

PASSWORD_POLICY = cognito.PasswordPolicy(
    min_length=8,
    require_lowercase=True,
    require_uppercase=True,
    require_digits=True,
    require_symbols=True,
)


class AuthStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        otp_mode = self.node.try_get_context("otpMode") or "fixed"
        if otp_mode not in ("fixed", "sms"):
            raise ValueError(f"otpMode must be 'fixed' or 'sms', got {otp_mode!r}")

        self._build_business_pool()
        self._build_customer_pool(otp_mode)
        self._suppress_nag()

    # --- helpers ------------------------------------------------------------

    def _function(self, construct_id: str, folder: str, environment: dict | None = None) -> lambda_.Function:
        return lambda_.Function(
            self,
            construct_id,
            runtime=RUNTIME,
            architecture=lambda_.Architecture.ARM_64,
            handler="handler.handler",
            code=lambda_.Code.from_asset(str(FUNCTIONS_DIR / folder)),
            timeout=Duration.seconds(5),
            memory_size=256,
            environment=environment or {},
            log_group=logs.LogGroup(
                self,
                f"{construct_id}Logs",
                retention=logs.RetentionDays.ONE_MONTH,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

    # --- business pool ------------------------------------------------------

    def _build_business_pool(self) -> None:
        self.business_pool = cognito.UserPool(
            self,
            "BusinessPool",
            user_pool_name="sumaat-business",
            feature_plan=cognito.FeaturePlan.ESSENTIALS,
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True)
            ),
            custom_attributes={"restaurantId": cognito.StringAttribute(mutable=True)},
            password_policy=PASSWORD_POLICY,
            mfa=cognito.Mfa.OFF,
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,
        )

        for group in ("owner", "cashier"):
            cognito.CfnUserPoolGroup(
                self,
                f"{group.capitalize()}Group",
                user_pool_id=self.business_pool.user_pool_id,
                group_name=group,
            )

        self.business_client = self.business_pool.add_client(
            "BusinessWebClient",
            user_pool_client_name="web",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_srp=True),
            prevent_user_existence_errors=True,
            read_attributes=cognito.ClientAttributes()
            .with_standard_attributes(email=True, email_verified=True)
            .with_custom_attributes("restaurantId"),
            # restaurantId is deliberately NOT writable: only the API sets it (Admin APIs).
            write_attributes=cognito.ClientAttributes().with_standard_attributes(email=True),
        )

        post_confirmation = self._function("PostConfirmationFn", "post_confirmation")
        self.business_pool.add_trigger(cognito.UserPoolOperation.POST_CONFIRMATION, post_confirmation)

        # Separate Policy + wildcard pool ARN: referencing business_pool.user_pool_arn here
        # would create a pool <-> Lambda circular dependency.
        self._post_confirmation_policy = iam.Policy(
            self,
            "PostConfirmationPolicy",
            statements=[
                iam.PolicyStatement(
                    actions=["cognito-idp:AdminAddUserToGroup"],
                    resources=[f"arn:aws:cognito-idp:{self.region}:{self.account}:userpool/*"],
                )
            ],
        )
        post_confirmation.role.attach_inline_policy(self._post_confirmation_policy)

        CfnOutput(self, "BusinessUserPoolId", value=self.business_pool.user_pool_id)
        CfnOutput(self, "BusinessClientId", value=self.business_client.user_pool_client_id)

    # --- customer pool ------------------------------------------------------

    def _build_customer_pool(self, otp_mode: str) -> None:
        self.customer_pool = cognito.UserPool(
            self,
            "CustomerPool",
            user_pool_name="sumaat-customers",
            feature_plan=cognito.FeaturePlan.ESSENTIALS,
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(phone=True),
            standard_attributes=cognito.StandardAttributes(
                phone_number=cognito.StandardAttribute(required=True, mutable=True),
                fullname=cognito.StandardAttribute(required=True, mutable=True),
            ),
            # Required by the SignUp API; the website sends a random one nobody uses.
            password_policy=PASSWORD_POLICY,
            mfa=cognito.Mfa.OFF,
            account_recovery=cognito.AccountRecovery.NONE,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.customer_client = self.customer_pool.add_client(
            "CustomerWebClient",
            user_pool_client_name="web",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(custom=True),  # phone + OTP only, no password login
            prevent_user_existence_errors=True,
            read_attributes=cognito.ClientAttributes().with_standard_attributes(
                fullname=True, phone_number=True, phone_number_verified=True
            ),
            write_attributes=cognito.ClientAttributes().with_standard_attributes(
                fullname=True, phone_number=True
            ),
        )

        customer_auth = self._function(
            "CustomerAuthFn",
            "customer_auth",
            environment={"OTP_MODE": otp_mode, "FIXED_OTP": "1234"},
        )
        for op in (
            cognito.UserPoolOperation.PRE_SIGN_UP,
            cognito.UserPoolOperation.DEFINE_AUTH_CHALLENGE,
            cognito.UserPoolOperation.CREATE_AUTH_CHALLENGE,
            cognito.UserPoolOperation.VERIFY_AUTH_CHALLENGE_RESPONSE,
        ):
            self.customer_pool.add_trigger(op, customer_auth)

        # SMS publishing to a phone number has no resource ARN, so it must be "*".
        customer_auth.add_to_role_policy(
            iam.PolicyStatement(actions=["sns:Publish"], resources=["*"])
        )

        CfnOutput(self, "CustomerUserPoolId", value=self.customer_pool.user_pool_id)
        CfnOutput(self, "CustomerClientId", value=self.customer_client.user_pool_client_id)

    # --- cdk-nag ------------------------------------------------------------

    def _suppress_nag(self) -> None:
        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-COG2",
                    "reason": "POC decision: no MFA. Business users sign in with email + password; "
                    "customers already prove their phone with an OTP on every login.",
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
                    "reason": "Lambda roles use the AWS-managed AWSLambdaBasicExecutionRole "
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
                    "id": "AwsSolutions-IAM5",
                    "reason": "sns:Publish directly to a phone number (SMS OTP) has no resource ARN.",
                    "appliesTo": ["Resource::*"],
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Python 3.14 is pinned project-wide (.python-version) so local tests "
                    "match the Lambda runtime; upgrade together later.",
                },
            ],
        )
