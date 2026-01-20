"""
Stripe決済サービス
月額サブスクリプション管理
"""
import stripe
from typing import Optional
from datetime import datetime, timedelta
from config import settings


class StripeService:
    def __init__(self):
        # Stripeシークレットキーを設定
        stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        self.price_id = getattr(settings, 'STRIPE_PRICE_ID', '')  # 月額1,980円のPrice ID

    def create_checkout_session(self, user_id: str, success_url: str, cancel_url: str) -> Optional[str]:
        """
        Checkout Sessionを作成して決済URLを取得

        Args:
            user_id: LINEユーザーID
            success_url: 決済成功時のリダイレクトURL
            cancel_url: 決済キャンセル時のリダイレクトURL

        Returns:
            決済URL（Stripe Checkout URL）
        """
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price': self.price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=user_id,  # LINEユーザーIDを紐付け
                metadata={
                    'user_id': user_id,
                }
            )
            return session.url
        except Exception as e:
            print(f"Stripe checkout session creation error: {e}", flush=True)
            return None

    def create_payment_link(self, user_id: str) -> Optional[str]:
        """
        簡単な決済リンクを作成（事前作成済みのPayment Linkを使用）

        Args:
            user_id: LINEユーザーID

        Returns:
            決済URL
        """
        # Stripeダッシュボードで作成したPayment LinkのURLを返す
        # ユーザーIDをクエリパラメータとして追加
        payment_link_id = getattr(settings, 'STRIPE_PAYMENT_LINK_ID', '')
        if payment_link_id:
            return f"https://buy.stripe.com/{payment_link_id}?client_reference_id={user_id}"
        return None

    def verify_webhook_signature(self, payload: bytes, signature: str) -> Optional[dict]:
        """
        Stripe Webhookの署名を検証

        Args:
            payload: リクエストボディ
            signature: Stripe-Signature ヘッダー

        Returns:
            イベントデータ
        """
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            return event
        except ValueError as e:
            print(f"Invalid payload: {e}", flush=True)
            return None
        except stripe.error.SignatureVerificationError as e:
            print(f"Invalid signature: {e}", flush=True)
            return None

    def get_subscription_end_date(self, subscription_id: str) -> Optional[datetime]:
        """
        サブスクリプションの終了日を取得

        Args:
            subscription_id: StripeサブスクリプションID

        Returns:
            終了日時
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            # current_period_endはUNIXタイムスタンプ
            return datetime.fromtimestamp(subscription.current_period_end)
        except Exception as e:
            print(f"Error retrieving subscription: {e}", flush=True)
            return None

    def cancel_subscription(self, subscription_id: str) -> bool:
        """
        サブスクリプションをキャンセル

        Args:
            subscription_id: StripeサブスクリプションID

        Returns:
            成功/失敗
        """
        try:
            stripe.Subscription.delete(subscription_id)
            return True
        except Exception as e:
            print(f"Error canceling subscription: {e}", flush=True)
            return False


# シングルトンインスタンス
stripe_service = StripeService()
