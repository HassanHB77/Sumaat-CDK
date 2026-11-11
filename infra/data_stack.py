"""DataStack: the single DynamoDB table `sumaat`.

Item shapes (see README / design doc):
  Restaurant  PK=RESTAURANT#<id>  SK=PROFILE   GSI1=GEO#<geohash5> / RESTAURANT#<id>
  Menu item   PK=RESTAURANT#<id>  SK=ITEM#<id>
  Order       PK=ORDER#<id>       SK=ORDER     GSI1=RORDERS#<rid> / <createdAt>
                                               GSI2=CORDERS#<sub> / <createdAt>
  Counter     PK=RESTAURANT#<id>  SK=COUNTER
  Owner lock  PK=OWNER#<sub>      SK=RESTAURANT  (one restaurant per owner; written with the profile)
  Config      PK=CONFIG           SK=CATEGORIES  categories={string set}  (menu categories)
"""

from aws_cdk import RemovalPolicy, Stack
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct

TABLE_NAME = "sumaat"


def _str(name: str) -> dynamodb.Attribute:
    return dynamodb.Attribute(name=name, type=dynamodb.AttributeType.STRING)


class DataStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.table = dynamodb.Table(
            self,
            "Table",
            table_name=TABLE_NAME,
            partition_key=_str("PK"),
            sort_key=_str("SK"),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
            # POC: tear down cleanly with `cdk destroy`. PITR still covers accidents.
            removal_policy=RemovalPolicy.DESTROY,
        )

        for n in (1, 2):
            self.table.add_global_secondary_index(
                index_name=f"GSI{n}",
                partition_key=_str(f"GSI{n}PK"),
                sort_key=_str(f"GSI{n}SK"),
                projection_type=dynamodb.ProjectionType.ALL,
            )
