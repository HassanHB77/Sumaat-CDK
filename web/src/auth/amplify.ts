import { Amplify } from 'aws-amplify'
import type { AppConfig } from '../config/config'

/** Amplify is used for Auth only (Cognito user pool, email + password). */
export function configureAmplify(config: AppConfig): void {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: config.userPoolId,
        userPoolClientId: config.userPoolClientId,
        loginWith: { email: true },
      },
    },
  })
}
