import type { MessageKey } from './en'

/** Arabic strings (same keys as en.ts). Digits stay Western (0-9) everywhere. */
export const ar: Record<MessageKey, string> = {
  'app.name': 'سماط',
  'app.tagline': 'اطلب مسبقًا، واستلم طازجًا',
  'lang.switch': 'EN',
  'lang.switchLabel': 'التبديل إلى الإنجليزية',

  'nav.restaurants': 'المطاعم',
  'nav.cart': 'السلة',
  'nav.orders': 'طلباتي',
  'nav.login': 'تسجيل الدخول',
  'nav.signup': 'إنشاء حساب',

  'home.find': 'اعثر على مطاعم قريبة منك',
  'home.owner': 'تملك مطعمًا؟ انضم إلى سماط',
  'home.step1': 'اختر',
  'home.step2': 'اطلب',
  'home.step3': 'استلم وادفع عند الكاشير',

  'page.restaurants': 'مطاعم قريبة منك',
  'page.menu': 'قائمة الطعام',
  'page.cart': 'سلتك',
  'page.login': 'تسجيل الدخول',
  'page.signup': 'أنشئ حسابك',
  'page.ownerSignup': 'سجّل مطعمك',
  'page.confirm': 'تأكيد بريدك الإلكتروني',
  'page.forgot': 'استعادة كلمة المرور',
  'page.orders': 'طلباتي',
  'page.order': 'الطلب',
  'page.owner': 'مطعمي',
  'page.ownerSetup': 'إعداد مطعمك',
  'page.ownerOrders': 'الطلبات',
  'page.ownerMenu': 'قائمة الطعام',
  'page.ownerRestaurant': 'بيانات المطعم',
  'page.ownerCashiers': 'موظفو الكاشير',
  'page.counter': 'شاشة الكاشير',

  'placeholder.comingIn': 'قريبًا في {milestone}',
  'notFound.title': 'الصفحة غير موجودة',
  'notFound.home': 'العودة إلى الرئيسية',

  'status.api': 'الخادم',
  'status.config': 'الإعدادات',
  'status.build': 'الإصدار',

  'error.config': 'تعذّر تحميل إعدادات التطبيق. يرجى تحديث الصفحة.',
  'error.network': 'لا يوجد اتصال — أعد المحاولة',
}
