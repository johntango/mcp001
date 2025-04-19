import stripe
import os

# Set your secret key. Remember to replace this with your actual secret key.
stripe.api_key = os.getenv("STRIPE_API_KEY")

# Example: Create a PaymentIntent
def create_payment_intent():
    try:
        intent = stripe.PaymentIntent.create(
            amount=2000,  # Amount in cents (e.g., $20.00)
            currency="usd",
            payment_method_types=["card"],
        )
        print("PaymentIntent created successfully:", intent)
    except stripe.error.StripeError as e:
        print("Stripe error:", e)

if __name__ == "__main__":
    create_payment_intent()
