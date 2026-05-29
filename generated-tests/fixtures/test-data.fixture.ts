import { test as base, expect } from '@playwright/test';
import usersData from '../test-data/users.json';
import productsData from '../test-data/products.json';
import checkoutData from '../test-data/checkout-data.json';

type UserRecord = {
  alias: string;
  username?: string;
  usernameEnv?: string;
  password?: string;
  passwordEnv?: string;
  role: string;
  status?: string;
};

type ProductRecord = {
  alias: string;
  sku: string;
  name: string;
  searchTerm: string;
  status?: string;
};

type ShippingAddress = {
  alias: string;
  line1: string;
  city: string;
  state: string;
  postalCode: string;
};

type TestData = {
  user: {
    username: string;
    password: string;
    role: string;
  };
  product: ProductRecord;
  shippingAddress: ShippingAddress;
};

const users = usersData as { users: UserRecord[] };
const products = productsData as { products: ProductRecord[] };
const checkout = checkoutData as { shippingAddresses: ShippingAddress[] };

function envValue(name?: string): string {
  return name ? process.env[name] ?? '' : '';
}

export const test = base.extend<{ testData: TestData }>({
  testData: async ({}, use) => {
    const user = users.users.find((item) => item.alias === 'validCustomer' || item.status === 'active');
    const product = products.products.find((item) => item.alias === 'inStockProduct' || item.status === 'inStock');
    const shippingAddress =
      checkout.shippingAddresses.find((item) => item.alias === 'qaShippingAddress') ??
      checkout.shippingAddresses[0];

    if (!user) {
      throw new Error('Required test data not found: valid customer user');
    }
    if (!product) {
      throw new Error('Required test data not found: in-stock product');
    }
    if (!shippingAddress) {
      throw new Error('Required test data not found: shipping address');
    }

    await use({
      user: {
        username: user.username || envValue(user.usernameEnv) || process.env.QA_CUSTOMER_USERNAME || '',
        password: envValue(user.passwordEnv) || user.password || process.env.QA_CUSTOMER_PASSWORD || '',
        role: user.role,
      },
      product,
      shippingAddress,
    });
  },
});

export { expect };
