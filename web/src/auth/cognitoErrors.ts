import type { MessageKey } from '../i18n/en'

/** Amplify/Cognito error -> a plain message key (EN/AR). Never show raw Cognito text to users. */
export function cognitoErrorKey(error: unknown): MessageKey {
  const e = error as { name?: string; message?: string } | null
  const name = e?.name ?? ''
  const message = e?.message ?? ''
  switch (name) {
    case 'NotAuthorizedException':
      return /disabled/i.test(message) ? 'auth.err.disabled' : 'auth.err.wrongCredentials'
    case 'UserNotFoundException':
      return 'auth.err.wrongCredentials' // don't reveal whether the email exists
    case 'UsernameExistsException':
    case 'AliasExistsException':
      return 'auth.err.emailTaken'
    case 'CodeMismatchException':
      return 'auth.err.codeWrong'
    case 'ExpiredCodeException':
      return 'auth.err.codeExpired'
    case 'LimitExceededException':
    case 'TooManyRequestsException':
    case 'TooManyFailedAttemptsException':
      return 'auth.err.tooMany'
    case 'InvalidPasswordException':
      return 'auth.err.password'
    case 'InvalidParameterException':
      return /phone/i.test(message) ? 'auth.err.phone' : 'auth.err.generic'
    case 'UserNotConfirmedException':
      return 'auth.err.notConfirmed'
    case 'NetworkError':
      return 'error.network'
    default:
      return 'auth.err.generic'
  }
}
